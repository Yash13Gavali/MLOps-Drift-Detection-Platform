"""Validated process configuration."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Load explicit operational limits without mutable global configuration."""

    root: Path
    api_key: str
    webhook: str | None = None
    window: int = 200
    minimum: int = 50
    interval: float = 30.0

    def __post_init__(self) -> None:
        if len(self.api_key) < 24:
            raise ValueError("API_KEY must contain at least 24 characters")
        if not 20 <= self.minimum <= self.window <= 10000:
            raise ValueError("Require 20 <= minimum <= window <= 10000")
        if self.interval < 1:
            raise ValueError("Monitor interval must be at least one second")
        if self.webhook and not self.webhook.startswith("https://"):
            raise ValueError("Alert webhooks require HTTPS")

    @classmethod
    def from_env(cls) -> "Settings":
        """Read environment settings and fail closed on invalid values."""
        return cls(
            root=Path(os.getenv("DATA_ROOT", "data")),
            api_key=os.environ.get("API_KEY", ""),
            webhook=os.getenv("ALERT_WEBHOOK") or None,
            window=int(os.getenv("DRIFT_WINDOW", "200")),
            minimum=int(os.getenv("DRIFT_MINIMUM", "50")),
            interval=float(os.getenv("MONITOR_INTERVAL", "30")),
        )

