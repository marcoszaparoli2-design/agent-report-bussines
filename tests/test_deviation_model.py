from datetime import date, timedelta

from src.anomaly_detection.deviation_model import compute_baseline
from src.data.sources.base import DataPoint


def test_baseline_median_and_zscore_for_stable_series():
    as_of = date(2024, 3, 10)
    history_dates = [as_of - timedelta(weeks=w) for w in range(1, 9)]
    series = [DataPoint(metric_date=d, entity="e", value=100.0) for d in history_dates]

    result = compute_baseline(series, as_of, today_value=100.0, window_days=56)

    assert result.median == 100.0
    assert result.z_score == 0.0
    assert result.sample_size == 8


def test_baseline_applies_relative_floor_when_mad_is_zero():
    as_of = date(2024, 3, 10)
    history_dates = [as_of - timedelta(weeks=w) for w in range(1, 9)]
    series = [DataPoint(metric_date=d, entity="e", value=100.0) for d in history_dates]

    result = compute_baseline(series, as_of, today_value=50.0, window_days=56, floor_fraction=0.05)

    assert result.scaled_mad == 5.0  # 0.05 * median(100), since MAD is 0
    assert result.z_score == (50.0 - 100.0) / 5.0


def test_baseline_only_uses_same_weekday_points_within_window():
    as_of = date(2024, 3, 10)
    same_weekday = [as_of - timedelta(weeks=w) for w in range(1, 4)]
    other_weekday = as_of - timedelta(days=1)
    out_of_window = as_of - timedelta(weeks=20)

    series = (
        [DataPoint(metric_date=d, entity="e", value=100.0) for d in same_weekday]
        + [DataPoint(metric_date=other_weekday, entity="e", value=999.0)]
        + [DataPoint(metric_date=out_of_window, entity="e", value=1.0)]
    )

    result = compute_baseline(series, as_of, today_value=100.0, window_days=56)

    assert result.sample_size == 3


def test_baseline_excludes_calendar_dates():
    as_of = date(2024, 3, 10)
    history_dates = [as_of - timedelta(weeks=w) for w in range(1, 5)]
    series = [DataPoint(metric_date=d, entity="e", value=100.0) for d in history_dates]
    excluded = frozenset({history_dates[0]})

    result = compute_baseline(series, as_of, today_value=100.0, window_days=56, calendar_exclusions=excluded)

    assert result.sample_size == 3


def test_cold_start_measured_in_calendar_days_not_filtered_sample_size():
    as_of = date(2024, 3, 10)
    earliest = as_of - timedelta(days=10)
    series = [DataPoint(metric_date=earliest, entity="e", value=100.0)]

    result = compute_baseline(series, as_of, today_value=100.0, window_days=56)

    assert result.history_days == 10
    assert result.sample_size == 0  # not same weekday as as_of, so no baseline sample


def test_no_history_returns_none_baseline():
    as_of = date(2024, 3, 10)

    result = compute_baseline([], as_of, today_value=100.0, window_days=56)

    assert result.median is None
    assert result.z_score is None
    assert result.history_days == 0
