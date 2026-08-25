"""Quality gates: decide whether a z-score is allowed to become severity.

Each gate suppresses severity without deleting the observation -- the raw
z-score and the reason it was suppressed both survive into the audit trail.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.anomaly_detection.deviation_model import BaselineResult
from src.data.metric_schema import MetricContract

Severity = Literal["none", "watch", "high"]


@dataclass(frozen=True)
class GatedSignal:
    severity: Severity
    flags: tuple[str, ...]
    z_score: float | None


def apply_gates(
    baseline: BaselineResult,
    contract: MetricContract,
    entity_share_of_total: float | None = None,
) -> GatedSignal:
    flags: list[str] = []

    if baseline.median is None or baseline.z_score is None:
        return GatedSignal(severity="none", flags=("insufficient_history",), z_score=None)

    if baseline.history_days < contract.min_history_days:
        flags.append("cold_start")

    if (
        entity_share_of_total is not None
        and contract.min_volume_share > 0
        and entity_share_of_total < contract.min_volume_share
    ):
        flags.append("low_volume")

    if flags:
        return GatedSignal(severity="none", flags=tuple(flags), z_score=baseline.z_score)

    abs_z = abs(baseline.z_score)
    if abs_z >= contract.severity.high:
        severity: Severity = "high"
    elif abs_z >= contract.severity.watch:
        severity = "watch"
    else:
        severity = "none"

    return GatedSignal(severity=severity, flags=(), z_score=baseline.z_score)
