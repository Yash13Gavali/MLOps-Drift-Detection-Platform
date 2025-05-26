"""Inference and monitoring orchestration."""

import asyncio
import logging
import threading
import numpy as np
from drift_platform.alerts import deliver
from drift_platform.artifacts import Model
from drift_platform.config import Settings
from drift_platform.drift import compare
from drift_platform.schemas import PredictionRequest, PredictionResponse
from drift_platform.storage import Store

LOGGER = logging.getLogger(__name__)


class Service:
    """Serve an immutable model and monitor committed inference observations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = Model(settings.root / "models")
        if len(self.model.reference) < settings.minimum:
            raise ValueError("Reference dataset is smaller than DRIFT_MINIMUM")
        self.store = Store(settings.root / "features.sqlite3")
        self.lock = threading.Lock()
        self.monitor_healthy = True

    def predict(self, request: PredictionRequest) -> PredictionResponse:
        """Predict and durably record every accepted feature row."""
        rows = [observation.vector() for observation in request.observations]
        predictions, probabilities = self.model.predict(np.asarray(rows, dtype=float))
        self.store.append(self.model.version, rows)
        return PredictionResponse(model_version=self.model.version,
                                  predictions=predictions, probabilities=probabilities)

    def monitor(self) -> dict | None:
        """Evaluate a complete window without prematurely consuming partial data."""
        with self.lock:
            end_id, rows = self.store.window(self.model.version, self.settings.window)
            if len(rows) < self.settings.window:
                return None
            report = compare(self.model.reference, np.asarray(rows, dtype=float), self.settings.minimum)
            self.store.record(self.model.version, end_id, report)
            return report

    async def run(self, stop: asyncio.Event) -> None:
        """Run bounded monitoring and alert delivery until graceful shutdown."""
        while not stop.is_set():
            try:
                await asyncio.to_thread(self.monitor)
                await deliver(self.store, self.settings.webhook)
                self.monitor_healthy = True
            except Exception:
                self.monitor_healthy = False
                LOGGER.exception("Monitoring cycle failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.settings.interval)
            except TimeoutError:
                continue
