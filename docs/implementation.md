# Complete project implementation

# Sequential implementation phases

| Phase | Implementation | Acceptance criterion |
| --- | --- | --- |
| 01 | Package and repository structure | Installable `src` package and CLI |
| 02 | Typed configuration | Invalid secrets and window limits fail startup |
| 03 | Dependency pins | Runtime and test versions specified explicitly |
| 04 | Shared Docker image | Training and serving run the same image |
| 05 | Environment fingerprint | Changed interpreter or packages rejects artifact |
| 06 | Feature schema | Four ordered, finite, bounded numeric features |
| 07 | Feature logging | Entire inference batch commits transactionally |
| 08 | Reproducible data | Bundled Iris data with fixed stratified split |
| 09 | Training input validation | NPZ data follows feature and class contract |
| 10 | Model training | Standardization and multinomial logistic regression |
| 11 | Evaluation | Held-out accuracy and log loss recorded |
| 12 | Promotion gate | Accuracy at least 0.90 and log loss at most 0.40 |
| 13 | Model registry | Content-addressed immutable JSON bundles |
| 14 | Integrity validation | Corruption and invalid dimensions fail startup |
| 15 | Reference distribution | Training-only reference rows accompany model |
| 16 | KS engine | Two-sample tests run independently per feature |
| 17 | Trigger policy | Any statistic strictly greater than 0.10 alerts |
| 18 | Report persistence | Unique model/window checkpoints prevent repeats |
| 19 | Alert outbox | Alert insertion and checkpoint share a transaction |
| 20 | Webhook transport | Bounded HTTPS retries and stable delivery keys |
| 21 | Inference service | Stable softmax and canonical class mapping |
| 22 | Health endpoints | Readiness checks model, database, and monitor |
| 23 | API controls | Constant-time key comparison and bounded payloads |
| 24 | Metrics | Request counts, duration sum, reports, pending alerts |
| 25 | Automated monitor | Complete windows processed during API lifecycle |
| 26 | Lifecycle CLI | Train, serve, monitor, and smoke commands |
| 27 | Automated tests | Boundaries, failures, restart recovery, HTTP contracts |
| 28 | CI automation | Container build followed by tests in that image |
| 29 | Release validation | Authenticated smoke inference within measured budget |
| 30 | Operations | Deployment, rollback, alert triage, and backup procedures |


## Directory tree


```text
.
├── .github/workflows/ci.yml
├── .dockerignore
├── .gitignore
├── Dockerfile
├── compose.yaml
├── pyproject.toml
├── requirements.lock
├── README.md
├── docs/
│   ├── implementation.md
│   ├── phases.md
│   └── operations.md
├── src/drift_platform/
│   ├── __init__.py
│   ├── config.py
│   ├── schemas.py
│   ├── environment.py
│   ├── artifacts.py
│   ├── training.py
│   ├── drift.py
│   ├── storage.py
│   ├── alerts.py
│   ├── service.py
│   ├── api.py
│   └── cli.py
└── tests/
    ├── test_drift.py
    └── test_lifecycle.py
```



## Full source files


### pyproject.toml

```toml
[build-system]
requires = ["setuptools==80.9.0"]
build-backend = "setuptools.build_meta"

[project]
name = "mlops-drift-platform"
version = "1.0.0"
description = "Reproducible training, inference, and distribution monitoring"
requires-python = ">=3.11,<3.13"
dependencies = ["fastapi==0.116.1", "uvicorn==0.35.0", "numpy==2.2.6", "scipy==1.15.3", "scikit-learn==1.6.1", "httpx==0.28.1", "pydantic==2.11.7"]

[project.scripts]
drift-platform = "drift_platform.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```


### requirements.lock

```text
annotated-types==0.7.0
anyio==4.9.0
certifi==2025.8.3
click==8.2.1
colorama==0.4.6; sys_platform == "win32"
fastapi==0.116.1
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.10
iniconfig==2.1.0
joblib==1.5.1
numpy==2.2.6
packaging==25.0
pluggy==1.6.0
pydantic==2.11.7
pydantic_core==2.33.2
Pygments==2.19.2
pytest==8.4.1
scikit-learn==1.6.1
scipy==1.15.3
setuptools==80.9.0
sniffio==1.3.1
starlette==0.47.2
threadpoolctl==3.6.0
typing_extensions==4.14.1
typing-inspection==0.4.1
uvicorn==0.35.0
```


### Dockerfile

```text
FROM python:3.11.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_ROOT=/data
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
COPY src ./src
COPY tests ./tests
RUN pip install --no-cache-dir --no-deps --no-build-isolation . \
    && useradd --uid 10001 --create-home platform \
    && mkdir /data && chown platform:platform /data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"
ENTRYPOINT ["drift-platform"]
CMD ["serve"]
```


### compose.yaml

```yaml
services:
  train:
    image: ${PLATFORM_IMAGE:-drift-platform:local}
    build: .
    command: ["train", "--root", "/data"]
    volumes:
      - platform-data:/data
    read_only: true
    tmpfs:
      - /tmp
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
  api:
    image: ${PLATFORM_IMAGE:-drift-platform:local}
    command: ["serve"]
    depends_on:
      train:
        condition: service_completed_successfully
    environment:
      API_KEY: ${API_KEY:?Set a secret with at least 24 characters}
      ALERT_WEBHOOK: ${ALERT_WEBHOOK:-}
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - platform-data:/data
    read_only: true
    tmpfs:
      - /tmp
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
    restart: unless-stopped
    mem_limit: 1g
    cpus: 2
volumes:
  platform-data:
```


### .github/workflows/ci.yml

```yaml
name: Validate and release
on:
  push:
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: validate-${{ github.ref }}
  cancel-in-progress: true
jobs:
  validate:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - name: Build the shared training and serving image
        run: docker build -t platform:${{ github.sha }} .
      - name: Run tests in the release image
        run: docker run --rm --entrypoint python platform:${{ github.sha }} -m pytest -q
      - name: Train and validate time to inference
        shell: bash
        run: |
          set -euo pipefail
          START=$SECONDS
          KEY=$(openssl rand -hex 24)
          echo "::add-mask::$KEY"
          docker volume create validation-data
          docker run --rm -v validation-data:/data platform:${{ github.sha }} train --root /data
          docker run -d --name platform-api -e API_KEY="$KEY" -v validation-data:/data platform:${{ github.sha }}
          ready=false
          for attempt in $(seq 1 30); do
            if docker exec -e API_KEY="$KEY" platform-api drift-platform smoke; then
              ready=true
              break
            fi
            sleep 2
          done
          test "$ready" = true
          ELAPSED=$((SECONDS - START))
          echo "Training-to-validated-inference: ${ELAPSED} seconds" >> "$GITHUB_STEP_SUMMARY"
          test "$ELAPSED" -le 300
      - name: Export validated image
        run: docker save platform:${{ github.sha }} | gzip > platform-image.tar.gz
      - uses: actions/upload-artifact@v4
        with:
          name: validated-container
          path: platform-image.tar.gz
          retention-days: 7
      - name: Cleanup
        if: always()
        run: |
          docker logs platform-api || true
          docker rm -f platform-api || true
          docker volume rm validation-data || true
```


### .dockerignore

```text
.git
.venv
__pycache__
.pytest_cache
data
.env
*.egg-info
```


### .gitignore

```text
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
*.egg-info/
build/
dist/
data/
.env
```


### src/drift_platform/__init__.py

```python
"""Model lifecycle and drift monitoring platform."""
```


### src/drift_platform/alerts.py

```python
"""Bounded asynchronous, at-least-once webhook delivery."""

import asyncio
import logging
import httpx
from drift_platform.storage import Store

LOGGER = logging.getLogger(__name__)


async def deliver(store: Store, webhook: str | None) -> None:
    """Retry pending alerts; consumers deduplicate the stable idempotency key."""
    if webhook is None:
        return
    async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client:
        for identifier, payload, attempts in await asyncio.to_thread(store.pending):
            success = False
            for retry in range(3):
                try:
                    response = await client.post(webhook, content=payload,
                        headers={"Content-Type": "application/json", "Idempotency-Key": f"drift-{identifier}"})
                    response.raise_for_status()
                    success = True
                except httpx.HTTPError:
                    LOGGER.warning("Alert delivery failed for report %s attempt %s", identifier, attempts + retry + 1)
                await asyncio.to_thread(store.attempted, identifier, success)
                if success:
                    break
                if retry < 2:
                    await asyncio.sleep(2 ** retry)
```


### src/drift_platform/api.py

```python
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
```


### src/drift_platform/artifacts.py

```python
"""Immutable, checksummed model bundles without executable serialization."""

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
import numpy as np
from numpy.typing import NDArray
from scipy.special import softmax
from drift_platform.environment import fingerprint
from drift_platform.schemas import FEATURES


def publish(root: Path, payload: dict) -> str:
    """Atomically publish a content-addressed JSON model and active pointer."""
    root.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()
    version = hashlib.sha256(raw).hexdigest()
    staging = Path(tempfile.mkdtemp(prefix="bundle-", dir=root))
    try:
        (staging / "model.json").write_bytes(raw)
        destination = root / version
        if not destination.exists():
            staging.rename(destination)
        with tempfile.NamedTemporaryFile(mode="w", dir=root, delete=False) as handle:
            handle.write(version)
            pointer = Path(handle.name)
        os.replace(pointer, root / "active")
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return version


class Model:
    """Validated linear classifier and its training reference distribution."""

    def __init__(self, root: Path) -> None:
        self.version = (root / "active").read_text().strip()
        if not re.fullmatch(r"[a-f0-9]{64}", self.version):
            raise ValueError("Invalid active model identifier")
        raw = (root / self.version / "model.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != self.version:
            raise ValueError("Model integrity validation failed")
        data = json.loads(raw)
        if data["environment"] != fingerprint():
            raise ValueError("Training and serving environments differ")
        if data["features"] != list(FEATURES) or data["format"] != 1:
            raise ValueError("Unsupported model schema")
        self.mean = np.asarray(data["mean"], dtype=float)
        self.scale = np.asarray(data["scale"], dtype=float)
        self.coef = np.asarray(data["coef"], dtype=float)
        self.intercept = np.asarray(data["intercept"], dtype=float)
        self.classes = np.asarray(data["classes"], dtype=int)
        self.reference = np.asarray(data["reference"], dtype=float)
        arrays = (self.mean, self.scale, self.coef, self.intercept, self.reference)
        if not all(np.isfinite(a).all() for a in arrays):
            raise ValueError("Non-finite artifact values")
        if (self.mean.shape != (4,) or self.scale.shape != (4,)
                or (self.scale <= 0).any() or self.coef.shape != (3, 4)
                or self.intercept.shape != (3,) or self.classes.tolist() != [0, 1, 2]
                or self.reference.ndim != 2 or self.reference.shape[1] != 4
                or len(self.reference) < 50):
            raise ValueError("Invalid artifact dimensions")

    def predict(self, values: NDArray[np.float64]) -> tuple[list[int], list[list[float]]]:
        """Compute stable multinomial probabilities using validated coefficients."""
        if values.ndim != 2 or values.shape[1] != 4 or not np.isfinite(values).all():
            raise ValueError("Invalid inference matrix")
        probabilities = softmax(((values - self.mean) / self.scale) @ self.coef.T + self.intercept, axis=1)
        return self.classes[probabilities.argmax(axis=1)].tolist(), probabilities.tolist()
```


### src/drift_platform/cli.py

```python
"""Command-line lifecycle operations."""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from time import perf_counter
import httpx
import uvicorn
from drift_platform.config import Settings
from drift_platform.service import Service
from drift_platform.training import train


def main() -> None:
    """Execute training, monitoring, serving, or an authenticated smoke check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["train", "serve", "monitor", "smoke"])
    parser.add_argument("--root", type=Path, default=Path("data"))
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        if args.command == "train":
            print(json.dumps(train(args.root / "models", args.dataset)))
        elif args.command == "serve":
            uvicorn.run("drift_platform.api:create_app", factory=True, host="0.0.0.0", port=8000,
                        workers=1, limit_concurrency=64, timeout_keep_alive=5, access_log=False)
        elif args.command == "monitor":
            service = Service(Settings.from_env())
            print(json.dumps(service.monitor()))
            from drift_platform.alerts import deliver
            asyncio.run(deliver(service.store, service.settings.webhook))
        else:
            settings = Settings.from_env()
            started = perf_counter()
            with httpx.Client(base_url=args.url, timeout=10, trust_env=False) as client:
                client.get("/health/ready").raise_for_status()
                response = client.post("/predict", headers={"X-API-Key": settings.api_key},
                    json={"observations": [{"sepal_length": 5.1, "sepal_width": 3.5,
                                            "petal_length": 1.4, "petal_width": 0.2}]})
                response.raise_for_status()
                if response.json()["predictions"] != [0]:
                    raise ValueError("Smoke prediction violated expected class")
            print(json.dumps({"smoke_seconds": perf_counter() - started, "status": "passed"}))
    except Exception as error:
        logging.getLogger(__name__).error("Operation failed: %s", error)
        sys.exit(1)
```


### src/drift_platform/config.py

```python
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
```


### src/drift_platform/drift.py

```python
"""Two-sample KS monitoring with a fixed engineering effect-size threshold."""

import numpy as np
import math
from numpy.typing import NDArray
from scipy.stats import ks_2samp
from drift_platform.schemas import FEATURES

THRESHOLD = 0.10


def compare(reference: NDArray[np.float64], current: NDArray[np.float64], minimum: int = 50) -> dict:
    """Alert when any feature's KS statistic strictly exceeds 0.10.

    P-values are diagnostic only; they do not replace the effect-size policy.
    Insufficient samples raise an error instead of declaring a healthy window.
    """
    for matrix in (reference, current):
        if matrix.ndim != 2 or matrix.shape[1] != len(FEATURES):
            raise ValueError("Expected a matrix with four canonical features")
        if len(matrix) < minimum or not np.isfinite(matrix).all():
            raise ValueError("Insufficient samples or non-finite measurements")
    results = []
    for index, name in enumerate(FEATURES):
        result = ks_2samp(reference[:, index], current[:, index], method="asymp")
        statistic = float(result.statistic)
        exceeds = statistic > THRESHOLD and not math.isclose(statistic, THRESHOLD, rel_tol=0, abs_tol=1e-12)
        results.append({"feature": name, "statistic": statistic,
                        "p_value": float(result.pvalue), "drifted": exceeds})
    return {"threshold": THRESHOLD, "reference_count": len(reference),
            "current_count": len(current), "drifted": any(r["drifted"] for r in results),
            "features": results}
```


### src/drift_platform/environment.py

```python
"""Verify interpreter, platform, and installed-distribution parity."""

import hashlib
import importlib.metadata
import json
import platform


def fingerprint() -> str:
    """Hash the complete installed package inventory and Python platform."""
    inventory = sorted((d.metadata["Name"].lower(), d.version) for d in importlib.metadata.distributions())
    payload = {"python": platform.python_version(), "system": platform.system(),
               "machine": platform.machine(), "packages": inventory}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
```


### src/drift_platform/schemas.py

```python
"""Inference and monitoring contracts."""

from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field

FEATURES = ("sepal_length", "sepal_width", "petal_length", "petal_width")
Finite = Annotated[float, Field(allow_inf_nan=False, ge=0, le=100)]


class Observation(BaseModel):
    """Strict ordered measurements for the bundled reference classifier."""

    model_config = ConfigDict(extra="forbid", strict=True)
    sepal_length: Finite
    sepal_width: Finite
    petal_length: Finite
    petal_width: Finite

    def vector(self) -> list[float]:
        """Return the canonical training feature order."""
        return [getattr(self, name) for name in FEATURES]


class PredictionRequest(BaseModel):
    """Bound a single inference batch."""

    model_config = ConfigDict(extra="forbid")
    observations: list[Observation] = Field(min_length=1, max_length=256)


class PredictionResponse(BaseModel):
    """Identify the immutable model used for every prediction."""

    model_version: str
    predictions: list[int]
    probabilities: list[list[float]]
```


### src/drift_platform/service.py

```python
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
```


### src/drift_platform/storage.py

```python
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
```


### src/drift_platform/training.py

```python
"""Deterministic training and held-out promotion validation."""

from pathlib import Path
import numpy as np
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from drift_platform.artifacts import publish
from drift_platform.environment import fingerprint
from drift_platform.schemas import FEATURES


def train(root: Path, dataset: Path | None = None) -> dict:
    """Train from an NPZ with X/y arrays or the bundled reproducible Iris data."""
    if dataset is None:
        values, labels = load_iris(return_X_y=True)
    else:
        with np.load(dataset, allow_pickle=False) as archive:
            values, labels = archive["X"], archive["y"]
    if (values.ndim != 2 or values.shape[1] != 4 or len(values) < 100
            or labels.shape != (len(values),) or not np.isfinite(values).all()
            or (values < 0).any() or (values > 100).any()
            or sorted(np.unique(labels).tolist()) != [0, 1, 2]):
        raise ValueError("Dataset violates feature or class contract")
    x_train, x_test, y_train, y_test = train_test_split(values, labels, test_size=0.25, random_state=42, stratify=labels)
    scaler = StandardScaler().fit(x_train)
    model = LogisticRegression(max_iter=1000, random_state=42).fit(scaler.transform(x_train), y_train)
    probabilities = model.predict_proba(scaler.transform(x_test))
    accuracy = float(accuracy_score(y_test, model.classes_[probabilities.argmax(axis=1)]))
    loss = float(log_loss(y_test, probabilities))
    if accuracy < 0.90 or loss > 0.40:
        raise ValueError(f"Promotion rejected: accuracy={accuracy:.4f}, log_loss={loss:.4f}")
    payload = {"format": 1, "features": list(FEATURES), "environment": fingerprint(),
               "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
               "coef": model.coef_.tolist(), "intercept": model.intercept_.tolist(),
               "classes": model.classes_.tolist(), "reference": x_train.tolist(),
               "metrics": {"accuracy": accuracy, "log_loss": loss}}
    version = publish(root, payload)
    return {"version": version, **payload["metrics"]}
```


### tests/test_drift.py

```python
"""Effect-size boundary and invalid-data regression checks."""

import numpy as np
import pytest
from drift_platform.drift import compare


def test_identical_and_shifted() -> None:
    """Identical data stays healthy; separated data triggers every feature."""
    reference = np.tile(np.arange(100, dtype=float)[:, None], (1, 4))
    assert not compare(reference, reference)["drifted"]
    assert compare(reference, reference + 200)["drifted"]


def test_exact_boundary() -> None:
    """The trigger is strictly greater than ten percent."""
    reference = np.zeros((100, 4))
    current = reference.copy()
    current[:10] = 1
    assert not compare(reference, current)["drifted"]
    current[10] = 1
    assert compare(reference, current)["drifted"]


def test_boundary_roundoff() -> None:
    """Floating point subtraction at the boundary cannot produce an alert."""
    reference = np.tile(np.arange(100, dtype=float)[:, None], (1, 4))
    assert not compare(reference, reference + 10)["drifted"]


@pytest.mark.parametrize("current", [np.zeros((10, 4)), np.zeros((100, 3)), np.full((100, 4), np.nan)])
def test_invalid_windows(current: np.ndarray) -> None:
    """Invalid windows cannot silently become healthy reports."""
    with pytest.raises(ValueError):
        compare(np.zeros((100, 4)), current)
```


### tests/test_lifecycle.py

```python
"""Exercise model gates, HTTP contracts, logging, and durable monitoring."""

import asyncio
from pathlib import Path
from unittest.mock import patch
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from drift_platform.alerts import deliver
from drift_platform.api import create_app
from drift_platform.artifacts import Model
from drift_platform.config import Settings
from drift_platform.service import Service
from drift_platform.training import train

KEY = "test-secret-with-at-least-24-characters"
ROW = {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Build an independently trained model and database for each case."""
    train(tmp_path / "models")
    return Settings(root=tmp_path, api_key=KEY, window=50, minimum=50)


def test_api_and_window(settings: Settings) -> None:
    """Validate auth, inference, monitoring, and outbox idempotency together."""
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/ready").status_code == 200
        assert client.post("/predict", json={"observations": [ROW]}).status_code == 401
        response = client.post("/predict", headers={"X-API-Key": KEY}, json={"observations": [ROW] * 50})
        assert response.status_code == 200
        assert response.json()["predictions"] == [0] * 50
        service = client.app.state.service
        assert service.monitor()["drifted"]
        assert service.monitor() is None
        assert len(service.store.pending()) == 1
        assert client.get("/drift", headers={"X-API-Key": KEY}).json()["drifted"]
        assert "alert_pending 1" in client.get("/metrics", headers={"X-API-Key": KEY}).text


def test_input_limits(settings: Settings) -> None:
    """Reject unknown fields, out-of-range values, and excessive payloads."""
    with TestClient(create_app(settings)) as client:
        for row in ({**ROW, "extra": 1}, {**ROW, "sepal_length": -1}):
            assert client.post("/predict", headers={"X-API-Key": KEY}, json={"observations": [row]}).status_code == 422
        assert client.post("/predict", content=b"x" * 131073).status_code == 413


def test_integrity_and_parity(settings: Settings) -> None:
    """Fail startup on mismatched environments and corrupted artifacts."""
    root = settings.root / "models"
    model = Model(root)
    with patch("drift_platform.artifacts.fingerprint", return_value="different"):
        with pytest.raises(ValueError, match="environments differ"):
            Model(root)
    artifact = root / model.version / "model.json"
    artifact.write_bytes(artifact.read_bytes() + b" ")
    with pytest.raises(ValueError, match="integrity"):
        Model(root)


def test_failed_promotion_preserves_active(settings: Settings, tmp_path: Path) -> None:
    """A failed quality gate cannot replace the serving model pointer."""
    root = settings.root / "models"
    before = (root / "active").read_text()
    dataset = tmp_path / "poor.npz"
    np.savez(dataset, X=np.ones((150, 4)), y=np.tile([0, 1, 2], 50))
    with pytest.raises(ValueError, match="Promotion rejected"):
        train(root, dataset)
    assert (root / "active").read_text() == before


def test_outbox_survives_restart(settings: Settings) -> None:
    """Pending reports survive service recreation and deliver with stable keys."""
    service = Service(settings)
    service.store.append(service.model.version, [[50.0] * 4] * 50)
    service.monitor()
    restarted = Service(settings)
    assert restarted.monitor() is None
    calls = []

    async def post(*args: object, **kwargs: object) -> httpx.Response:
        """Capture a delivery without external network access."""
        calls.append(kwargs)
        return httpx.Response(200, request=httpx.Request("POST", "https://alerts.example"))

    with patch("httpx.AsyncClient.post", side_effect=post):
        asyncio.run(deliver(restarted.store, "https://alerts.example"))
    assert calls[0]["headers"]["Idempotency-Key"] == "drift-1"
    assert restarted.store.pending() == []


def test_invalid_configuration() -> None:
    """Production auth and monitoring cannot start with unsafe configuration."""
    with pytest.raises(ValueError):
        Settings(root=Path("data"), api_key="short")


def test_export_matches_sklearn(settings: Settings) -> None:
    """Exported coefficients reproduce sklearn probabilities on held-out data."""
    from sklearn.datasets import load_iris
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    values, targets = load_iris(return_X_y=True)
    x_train, x_test, y_train, _ = train_test_split(values, targets, test_size=0.25, random_state=42, stratify=targets)
    scaler = StandardScaler().fit(x_train)
    classifier = LogisticRegression(max_iter=1000, random_state=42).fit(scaler.transform(x_train), y_train)
    model = Model(settings.root / "models")
    labels, probabilities = model.predict(x_test)
    assert np.allclose(probabilities, classifier.predict_proba(scaler.transform(x_test)), atol=1e-12)
    assert labels == classifier.predict(scaler.transform(x_test)).tolist()
    assert np.allclose(np.sum(probabilities, axis=1), 1)
    assert set(labels) == {0, 1, 2}


def test_failed_delivery_remains_pending(settings: Settings) -> None:
    """Transport failure records attempts without losing the queued alert."""
    service = Service(settings)
    service.store.append(service.model.version, [[50.0] * 4] * 50)
    service.monitor()
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("unavailable")), patch("drift_platform.alerts.asyncio.sleep"):
        asyncio.run(deliver(service.store, "https://alerts.example"))
    pending = service.store.pending()
    assert len(pending) == 1
    assert pending[0][2] == 3


def test_partial_window_is_not_consumed(settings: Settings) -> None:
    """A monitoring cycle waits for the entire configured sample window."""
    service = Service(settings)
    service.store.append(service.model.version, [[50.0] * 4] * 49)
    assert service.monitor() is None
    service.store.append(service.model.version, [[50.0] * 4])
    assert service.monitor()["current_count"] == 50


def test_storage_failure_returns_unavailable(settings: Settings) -> None:
    """Unlogged inference must never appear successful to the caller."""
    import sqlite3
    with TestClient(create_app(settings)) as client:
        with patch.object(client.app.state.service.store, "append", side_effect=sqlite3.OperationalError("disk full")):
            response = client.post("/predict", headers={"X-API-Key": KEY}, json={"observations": [ROW]})
        assert response.status_code == 503
```
