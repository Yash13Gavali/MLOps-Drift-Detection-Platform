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

