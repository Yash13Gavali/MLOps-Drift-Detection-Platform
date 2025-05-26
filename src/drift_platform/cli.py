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
