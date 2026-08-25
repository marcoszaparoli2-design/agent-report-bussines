"""Impact = deviation from baseline, never the raw value.

Normalizes an anomaly's "size" into a share of the day's primary volume, so
metrics of different types (a currency-style metric and a rate metric) can be
ranked side by side. Also computes the final relevance score used for
ranking, combining magnitude, impact, persistence, and confidence -- with
each factor's weight configurable.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.config import PriorityWeights

DEFAULT_SENSITIVITY_COEFFICIENT = 1.0


@dataclass(frozen=True)
class ImpactResult:
    impact_value: float
    impact_share: float
    used_default_sensitivity: bool


def compute_impact(
    delta_absolute: float,
    method: str,
    entity_volume: float | None,
    total_primary_volume: float | None,
    sensitivity_coefficient: float | None = None,
) -> ImpactResult:
    used_default_sensitivity = False

    if method == "direct_delta":
        impact_value = delta_absolute
    elif method == "exposure_weighted_rate":
        impact_value = delta_absolute * (entity_volume or 0.0)
    elif method == "business_sensitivity_weighted":
        coef = sensitivity_coefficient
        if coef is None:
            coef = DEFAULT_SENSITIVITY_COEFFICIENT
            used_default_sensitivity = True
        impact_value = delta_absolute * (entity_volume or 0.0) * coef
    else:
        raise ValueError(f"unknown impact method: {method}")

    if total_primary_volume in (None, 0):
        impact_share = 0.0
    else:
        impact_share = impact_value / total_primary_volume

    return ImpactResult(
        impact_value=impact_value,
        impact_share=impact_share,
        used_default_sensitivity=used_default_sensitivity,
    )


def compute_relevance(
    z_score: float,
    severity_high_threshold: float,
    impact_share: float,
    consecutive_days_off: int,
    confidence: float,
    sensitivity: float,
    weights: PriorityWeights,
) -> float:
    """relevance = (magnitude * w) * (impact * w) * (persistence * w) * (confidence * w) * sensitivity

    Every weight defaults to 1.0 and is configurable via
    config/detection_sensitivity.yaml (priority_weights).
    """
    magnitude = min(abs(z_score) / severity_high_threshold, 2.0)
    persistence_factor = 1.0 + min(consecutive_days_off, 30) * 0.05

    return (
        (magnitude * weights.magnitude)
        * (abs(impact_share) * weights.impact)
        * (persistence_factor * weights.persistence)
        * (confidence * weights.confidence)
        * sensitivity
    )
