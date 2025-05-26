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
