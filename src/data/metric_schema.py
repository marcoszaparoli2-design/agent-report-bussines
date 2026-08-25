"""Typed loader for metric contracts (metrics/<name>/contract.yaml).

Never decides a value -- pure schema loading and validation, so no threshold
or baseline number can hide inside Python code.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

Direction = Literal["higher_is_better", "lower_is_better"]
BaselineMethod = Literal["median_mad"]
ImpactMethod = Literal["direct_delta", "exposure_weighted_rate", "business_sensitivity_weighted"]

_VALID_DIRECTIONS = {"higher_is_better", "lower_is_better"}
_VALID_BASELINE_METHODS = {"median_mad"}
_VALID_IMPACT_METHODS = {"direct_delta", "exposure_weighted_rate", "business_sensitivity_weighted"}
_REQUIRED_FIELDS = {"name", "direction", "baseline_method", "impact_method", "dimension", "severity"}


class MetricContractError(ValueError):
    """Raised when a metric contract file is malformed or incomplete."""


@dataclass(frozen=True)
class SeverityThresholds:
    watch: float
    high: float

    def __post_init__(self) -> None:
        if self.watch <= 0 or self.high <= 0:
            raise MetricContractError("severity thresholds must be positive")
        if self.high < self.watch:
            raise MetricContractError("'high' threshold must be >= 'watch'")


@dataclass(frozen=True)
class MetricContract:
    name: str
    direction: Direction
    baseline_method: BaselineMethod
    impact_method: ImpactMethod
    dimension: str
    severity: SeverityThresholds
    window_days: int = 56
    min_history_days: int = 14
    min_volume_share: float = 0.0
    sensitivity: float = 1.0

    def bad_direction_sign(self) -> int:
        """+1 if a rise is the bad direction, -1 if a fall is the bad direction."""
        return -1 if self.direction == "higher_is_better" else 1


def load_contract(path: str | Path) -> MetricContract:
    """Load and validate a single metric contract from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise MetricContractError(f"contract file not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    missing = _REQUIRED_FIELDS - raw.keys()
    if missing:
        raise MetricContractError(f"contract {path} is missing required fields: {sorted(missing)}")

    if raw["direction"] not in _VALID_DIRECTIONS:
        raise MetricContractError(f"invalid direction '{raw['direction']}' in {path}")
    if raw["baseline_method"] not in _VALID_BASELINE_METHODS:
        raise MetricContractError(f"invalid baseline_method '{raw['baseline_method']}' in {path}")
    if raw["impact_method"] not in _VALID_IMPACT_METHODS:
        raise MetricContractError(f"invalid impact_method '{raw['impact_method']}' in {path}")

    severity_raw = raw["severity"]
    if not isinstance(severity_raw, dict) or "watch" not in severity_raw or "high" not in severity_raw:
        raise MetricContractError(f"contract {path} must declare severity.watch and severity.high")

    return MetricContract(
        name=raw["name"],
        direction=raw["direction"],
        baseline_method=raw["baseline_method"],
        impact_method=raw["impact_method"],
        dimension=raw["dimension"],
        severity=SeverityThresholds(watch=float(severity_raw["watch"]), high=float(severity_raw["high"])),
        window_days=int(raw.get("window_days", 56)),
        min_history_days=int(raw.get("min_history_days", 14)),
        min_volume_share=float(raw.get("min_volume_share", 0.0)),
        sensitivity=float(raw.get("sensitivity", 1.0)),
    )


def load_all_contracts(metrics_dir: str | Path) -> list[MetricContract]:
    """Load every metric contract found under metrics_dir/*/contract.yaml."""
    metrics_dir = Path(metrics_dir)
    return [load_contract(p) for p in sorted(metrics_dir.glob("*/contract.yaml"))]
