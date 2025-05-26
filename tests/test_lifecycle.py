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
