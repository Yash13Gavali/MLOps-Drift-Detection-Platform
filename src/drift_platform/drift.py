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
