"""Robust per-entity baseline + z-score.

Median + MAD instead of mean + stddev: resilient to outliers already present
in the history used as the reference. "Normal" is computed per entity, at
runtime, from that entity's own history -- never a hardcoded threshold.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date

from src.data.sources.base import DataPoint

_MAD_TO_STD = 1.4826  # scales MAD to be comparable to a standard deviation under normality


@dataclass(frozen=True)
class BaselineResult:
    median: float | None
    scaled_mad: float | None
    z_score: float | None
    history_days: int  # calendar-days of existence, NOT filtered sample size (cold-start measure)
    sample_size: int  # number of same-weekday points actually used for the baseline


def compute_baseline(
    entity_series: list[DataPoint],
    as_of_date: date,
    today_value: float,
    window_days: int,
    calendar_exclusions: frozenset[date] = frozenset(),
    floor_fraction: float = 0.05,
    epsilon: float = 1e-6,
) -> BaselineResult:
    """Compute the robust baseline and z-score of today_value against entity_series.

    entity_series may include today's own point or not -- it is ignored either
    way; only strictly-earlier, same-weekday, in-window, non-excluded dates
    feed the baseline.
    """
    if not entity_series:
        return BaselineResult(median=None, scaled_mad=None, z_score=None, history_days=0, sample_size=0)

    earliest_date = min(p.metric_date for p in entity_series)
    history_days = (as_of_date - earliest_date).days

    history_values = [
        p.value
        for p in entity_series
        if p.metric_date < as_of_date
        and p.metric_date.weekday() == as_of_date.weekday()
        and (as_of_date - p.metric_date).days <= window_days
        and p.metric_date not in calendar_exclusions
    ]

    if not history_values:
        return BaselineResult(
            median=None, scaled_mad=None, z_score=None, history_days=history_days, sample_size=0
        )

    median = statistics.median(history_values)
    mad = statistics.median([abs(v - median) for v in history_values])
    scaled_mad = max(_MAD_TO_STD * mad, floor_fraction * abs(median), epsilon)
    z_score = (today_value - median) / scaled_mad

    return BaselineResult(
        median=median,
        scaled_mad=scaled_mad,
        z_score=z_score,
        history_days=history_days,
        sample_size=len(history_values),
    )
