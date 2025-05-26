"""Transactional feature log, monitoring checkpoint, and alert outbox."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class Store:
    """Use a local durable database for a single serving replica."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY, version TEXT NOT NULL, features TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS observations_version ON observations(version, id);
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY, version TEXT NOT NULL, end_id INTEGER NOT NULL,
                    payload TEXT NOT NULL, UNIQUE(version, end_id));
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY REFERENCES reports(id), payload TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, delivered INTEGER NOT NULL DEFAULT 0);
            """)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Open a short-lived connection with bounded lock waiting."""
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def append(self, version: str, rows: list[list[float]]) -> None:
        """Commit the full inference batch before acknowledging success."""
        with self.connect() as db:
            db.executemany("INSERT INTO observations(version, features) VALUES (?, ?)",
                           [(version, json.dumps(row, allow_nan=False)) for row in rows])

    def window(self, version: str, size: int) -> tuple[int, list[list[float]]]:
        """Fetch the next unprocessed non-overlapping window for one model."""
        with self.connect() as db:
            rows = db.execute("""SELECT id, features FROM observations
                WHERE version=? AND id > COALESCE(
                    (SELECT MAX(end_id) FROM reports WHERE version=?), 0)
                ORDER BY id LIMIT ?""", (version, version, size)).fetchall()
        return (rows[-1][0], [json.loads(row[1]) for row in rows]) if rows else (0, [])

    def record(self, version: str, end_id: int, report: dict) -> bool:
        """Atomically checkpoint a report and enqueue drift alerts once."""
        payload = json.dumps({**report, "model_version": version, "end_id": end_id}, allow_nan=False)
        with self.connect() as db:
            cursor = db.execute("INSERT OR IGNORE INTO reports(version, end_id, payload) VALUES (?, ?, ?)",
                                (version, end_id, payload))
            if not cursor.rowcount:
                return False
            if report["drifted"]:
                db.execute("INSERT INTO outbox(id, payload) VALUES (?, ?)", (cursor.lastrowid, payload))
        return True

    def pending(self) -> list[tuple[int, str, int]]:
        """Return bounded pending deliveries; failed deliveries remain durable."""
        with self.connect() as db:
            return db.execute("SELECT id, payload, attempts FROM outbox WHERE delivered=0 ORDER BY id LIMIT 100").fetchall()

    def attempted(self, identifier: int, success: bool) -> None:
        """Persist delivery outcome without discarding unsuccessful alerts."""
        with self.connect() as db:
            db.execute("UPDATE outbox SET attempts=attempts+1, delivered=? WHERE id=?", (int(success), identifier))

    def latest(self) -> dict | None:
        """Read the most recently committed drift report."""
        with self.connect() as db:
            row = db.execute("SELECT payload FROM reports ORDER BY id DESC LIMIT 1").fetchone()
        return json.loads(row[0]) if row else None
