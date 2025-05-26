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

