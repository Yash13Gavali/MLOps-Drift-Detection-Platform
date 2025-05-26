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
