# MLOps Drift Detection Platform

A complete single-node reference implementation of deterministic model training, authenticated inference, statistical monitoring, and container-based release validation. The concrete model classifies Iris measurements; custom NPZ training data must satisfy the same four-feature, three-class contract.

## Engineering contracts

- Training, tests, and serving execute in the same Docker image. Artifact loading checks the complete installed-package, interpreter, and platform fingerprint. Promote the validated image by digest to preserve environment parity across hosts.
- A two-sample Kolmogorov–Smirnov statistic strictly greater than **0.10** on any feature creates a durable alert. This measures the maximum empirical CDF difference, not a percentage change in the mean. P-values are reported separately.
- CI measures training through successful authenticated inference and fails above **300 seconds**. Image build and download duration are excluded from this measurement and visible separately in CI. This is a validation budget, not a claimed production benchmark.

## 30 sequential phases

See [the complete phase breakdown](docs/phases.md) for the ordered implementation and acceptance criteria.

The [full implementation listing](docs/implementation.md) contains the complete source, container configuration, workflow, and tests in one document.

## Directory layout

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

## Run with Docker

Set `API_KEY` to a cryptographically random secret of at least 24 characters in your shell. Optionally set `ALERT_WEBHOOK` to an HTTPS receiver you control.

```sh
docker compose up --build -d
docker compose exec api drift-platform smoke
docker compose logs api
docker compose down
```

The training service must finish successfully before serving starts. Both services use the same image and persistent volume. The API binds to loopback on the host. The container runs as an unprivileged user with a read-only root filesystem and dropped capabilities.

## Local development

Use Python 3.11 or 3.12. Install the package before training so its distribution metadata participates in the environment fingerprint.

```sh
python -m venv .venv
python -m pip install -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pytest -q
drift-platform train
drift-platform serve
```

Activate the virtual environment before running the installation commands. Set `API_KEY` before serving. Local artifacts are intentionally incompatible with the Linux container; retrain in the release container.

## Inference

```sh
curl http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"observations":[{"sepal_length":5.1,"sepal_width":3.5,"petal_length":1.4,"petal_width":0.2}]}'
```

| Endpoint | Purpose | Authentication |
| --- | --- | --- |
| `POST /predict` | Bounded batch prediction and durable feature logging | API key |
| `GET /drift` | Latest completed monitoring report | API key |
| `GET /metrics` | Prometheus text counters and gauges | API key |
| `GET /health/live` | Process liveness | Public |
| `GET /health/ready` | Model, database, and monitor readiness | Public |

## Configuration

| Variable | Default | Contract |
| --- | --- | --- |
| `API_KEY` | Required | At least 24 characters |
| `DATA_ROOT` | `data` locally; `/data` in Docker | Writable persistent storage |
| `ALERT_WEBHOOK` | Unset | HTTPS; pending alerts remain queued if unset |
| `DRIFT_WINDOW` | 200 | Complete non-overlapping inference window |
| `DRIFT_MINIMUM` | 50 | Minimum valid sample count, at least 20 |
| `MONITOR_INTERVAL` | 30 seconds | At least one second |

The monitor processes one complete window per cycle. Provision capacity above ingestion rate and watch database growth. Pending deliveries retry with bounded backoff; the receiver must deduplicate `Idempotency-Key`. There is no automatic model replacement based on drift alone.

## Deployment boundary

This implementation targets one serving process and one local persistent database. Use a TLS reverse proxy with request deadlines and rate limits for external exposure. Horizontal replicas require shared transactional storage, distributed window claims, and an external monitoring worker. Environment parity does not imply identical CPU performance or identical infrastructure configuration.

The workflow exports the validated container as a GitHub artifact. No production destination or credentials were supplied, so it does not push to an external registry or mutate a production environment. Deployment and recovery procedures are in [operations](docs/operations.md).
Phase 6 update
Phase 7 update
Phase 8 update
Phase 9 update
Phase 10 update
Phase 11 update
Phase 12 update
Phase 13 update
Phase 14 update
Phase 15 update
Phase 16 update
Phase 17 update
Phase 18 update
Phase 19 update
Phase 20 update
Phase 21 update
Phase 22 update
Phase 23 update
Phase 24 update
Phase 25 update
Phase 26 update
Phase 27 update
Phase 28 update
Phase 29 update
