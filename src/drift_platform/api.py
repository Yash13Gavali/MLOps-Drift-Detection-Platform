"""Authenticated HTTP inference with bounded input and lifecycle monitoring."""

import asyncio
import hmac
import logging
import sqlite3
import threading
from contextlib import asynccontextmanager
from time import perf_counter
from typing import AsyncIterator
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from drift_platform.config import Settings
from drift_platform.schemas import PredictionRequest, PredictionResponse
from drift_platform.service import Service


class BodyLimit:
    """Enforce the body limit even when clients use chunked transfer encoding."""

    def __init__(self, app: ASGIApp, maximum: int = 131072) -> None:
        self.app = app
        self.maximum = maximum

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Read a bounded HTTP body before dispatching to the router."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.maximum:
                await JSONResponse({"detail": "Request body too large"}, status_code=413)(scope, receive, send)
                return
            chunks.append(message)
            if not message.get("more_body", False):
                break

        async def replay() -> Message:
            """Replay buffered bounded request messages to the application."""
            return chunks.pop(0) if chunks else await receive()

        await self.app(scope, replay, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an isolated application; startup validates artifacts and parity."""
    configuration = settings or Settings.from_env()
    counters = {"requests": 0, "seconds": 0.0, "errors": 0}
    lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        service = Service(configuration)
        app.state.service = service
        stop = asyncio.Event()
        task = asyncio.create_task(service.run(stop))
        try:
            yield
        finally:
            stop.set()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title="MLOps Drift Detection Platform", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BodyLimit)

    def authorize(x_api_key: str = Header(default="")) -> None:
        """Compare secret bytes in constant time and fail closed."""
        if not hmac.compare_digest(x_api_key.encode(), configuration.api_key.encode()):
            raise HTTPException(status_code=401, detail="Invalid API key")

    @app.get("/health/live")
    def live() -> dict:
        """Indicate that the HTTP process responds."""
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready() -> dict:
        """Check loaded model, monitoring health, and database connectivity."""
        service = app.state.service
        if not service.monitor_healthy:
            raise HTTPException(status_code=503, detail="Monitoring unavailable")
        try:
            with service.store.connect() as db:
                db.execute("SELECT 1")
        except sqlite3.Error as error:
            raise HTTPException(status_code=503, detail="Storage unavailable") from error
        return {"status": "ready", "model_version": service.model.version}

    @app.post("/predict", response_model=PredictionResponse, dependencies=[Depends(authorize)])
    def predict(request: PredictionRequest) -> PredictionResponse:
        """Return predictions only after feature logging succeeds."""
        started = perf_counter()
        try:
            return app.state.service.predict(request)
        except (sqlite3.Error, OSError) as error:
            with lock:
                counters["errors"] += 1
            logging.getLogger(__name__).exception("Inference persistence failed")
            raise HTTPException(status_code=503, detail="Inference storage unavailable") from error
        finally:
            with lock:
                counters["requests"] += 1
                counters["seconds"] += perf_counter() - started

    @app.get("/drift", dependencies=[Depends(authorize)])
    def drift() -> dict:
        """Expose the latest report or an explicit waiting state."""
        return app.state.service.store.latest() or {"status": "awaiting_complete_window"}

    @app.get("/metrics", response_class=PlainTextResponse, dependencies=[Depends(authorize)])
    def metrics() -> str:
        """Expose process-local Prometheus counters and monitoring gauges."""
        with lock:
            snapshot = dict(counters)
        store = app.state.service.store
        with store.connect() as db:
            pending = db.execute("SELECT COUNT(*) FROM outbox WHERE delivered=0").fetchone()[0]
            reports = db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        return (f"inference_requests_total {snapshot['requests']}\n"
                f"inference_duration_seconds_sum {snapshot['seconds']}\n"
                f"inference_storage_errors_total {snapshot['errors']}\n"
                f"drift_reports_total {reports}\nalert_pending {pending}\n"
                f"monitor_healthy {int(app.state.service.monitor_healthy)}\n")

    return app
