"""Persistence, tracked independently of the daily z-score.

Consecutive days on the same "bad" side of that day's own baseline (any
magnitude, no severity gate) catches a slow bleed that never spikes hard
enough on a single day to cross the severity threshold.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean

from src.anomaly_detection.deviation_model import compute_baseline
from src.data.metric_schema import MetricContract
from src.data.sources.base import DataPoint

Trend = str  # "worsening" | "stable" | "improving" | "unknown"


@dataclass(frozen=True)
class PersistenceResult:
    consecutive_days_off: int
    trend: dict[int, Trend]


def compute_persistence(
    entity_series: list[DataPoint],
    as_of_date: date,
    contract: MetricContract,
    max_days_back: int = 30,
    stable_relative_tolerance: float = 0.02,
) -> PersistenceResult:
    values_by_date = {p.metric_date: p.value for p in entity_series}
    bad_sign = contract.bad_direction_sign()

    consecutive_days_off = 0
    for offset in range(0, max_days_back + 1):
        check_date = as_of_date - timedelta(days=offset)
        if check_date not in values_by_date:
            break
        today_value = values_by_date[check_date]
        baseline = compute_baseline(entity_series, check_date, today_value, contract.window_days)
        if baseline.median is None:
            break
        deviation = today_value - baseline.median
        if (deviation * bad_sign) <= 0:
            break
        consecutive_days_off += 1

    trend: dict[int, Trend] = {}
    for window in contract_trend_windows():
        recent = [v for d, v in values_by_date.items() if 0 <= (as_of_date - d).days < window]
        prior = [v for d, v in values_by_date.items() if window <= (as_of_date - d).days < 2 * window]
        if not recent or not prior:
            trend[window] = "unknown"
            continue
        recent_avg = mean(recent)
        prior_avg = mean(prior)
        change = (recent_avg - prior_avg) * bad_sign
        if abs(prior_avg) > 1e-9 and abs(change / prior_avg) < stable_relative_tolerance:
            trend[window] = "stable"
        elif change > 0:
            trend[window] = "worsening"
        else:
            trend[window] = "improving"

    return PersistenceResult(consecutive_days_off=consecutive_days_off, trend=trend)


def contract_trend_windows() -> tuple[int, ...]:
    return (7, 15, 30)
