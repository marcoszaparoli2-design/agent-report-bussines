from datetime import date, timedelta

from src.anomaly_detection.streak_tracker import compute_persistence
from src.data.metric_schema import MetricContract, SeverityThresholds
from src.data.sources.base import DataPoint


def _contract(direction: str = "higher_is_better") -> MetricContract:
    return MetricContract(
        name="m",
        direction=direction,
        baseline_method="median_mad",
        impact_method="direct_delta",
        dimension="d",
        severity=SeverityThresholds(watch=2.0, high=3.0),
        window_days=56,
        min_history_days=1,
        min_volume_share=0.0,
        sensitivity=1.0,
    )


def test_consecutive_days_off_counts_a_streak_below_baseline():
    as_of = date(2024, 3, 10)
    points = []
    for offset in range(0, 60):
        current_date = as_of - timedelta(days=offset)
        value = 80.0 if offset in (0, 1, 2) else 100.0
        points.append(DataPoint(metric_date=current_date, entity="e", value=value))

    result = compute_persistence(points, as_of, _contract(), max_days_back=30)

    assert result.consecutive_days_off == 3


def test_consecutive_days_off_stops_at_first_normal_day():
    as_of = date(2024, 3, 10)
    points = []
    for offset in range(0, 60):
        current_date = as_of - timedelta(days=offset)
        value = 80.0 if offset == 0 else 100.0  # only "today" is off; yesterday was already back to normal
        points.append(DataPoint(metric_date=current_date, entity="e", value=value))

    result = compute_persistence(points, as_of, _contract(), max_days_back=30)

    assert result.consecutive_days_off == 1


def test_trend_worsening_when_recent_average_is_on_the_bad_side():
    as_of = date(2024, 3, 10)
    points = []
    for offset in range(0, 14):
        current_date = as_of - timedelta(days=offset)
        value = 80.0 if offset < 7 else 100.0  # recent week worse than prior week
        points.append(DataPoint(metric_date=current_date, entity="e", value=value))

    result = compute_persistence(points, as_of, _contract(), max_days_back=0)

    assert result.trend[7] == "worsening"


def test_trend_unknown_without_enough_history():
    as_of = date(2024, 3, 10)
    points = [DataPoint(metric_date=as_of, entity="e", value=100.0)]

    result = compute_persistence(points, as_of, _contract(), max_days_back=0)

    assert result.trend[30] == "unknown"
