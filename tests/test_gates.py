from src.anomaly_detection.deviation_model import BaselineResult
from src.anomaly_detection.gates import apply_gates
from src.data.metric_schema import MetricContract, SeverityThresholds


def _contract(**overrides) -> MetricContract:
    defaults = dict(
        name="m",
        direction="higher_is_better",
        baseline_method="median_mad",
        impact_method="direct_delta",
        dimension="d",
        severity=SeverityThresholds(watch=2.0, high=3.0),
        window_days=56,
        min_history_days=14,
        min_volume_share=0.0,
        sensitivity=1.0,
    )
    defaults.update(overrides)
    return MetricContract(**defaults)


def _baseline(z_score: float | None, history_days: int = 100) -> BaselineResult:
    return BaselineResult(median=100.0, scaled_mad=10.0, z_score=z_score, history_days=history_days, sample_size=8)


def test_severity_none_below_watch_threshold():
    result = apply_gates(_baseline(z_score=1.0), _contract())
    assert result.severity == "none"
    assert result.flags == ()


def test_severity_watch_and_high_thresholds():
    assert apply_gates(_baseline(z_score=2.5), _contract()).severity == "watch"
    assert apply_gates(_baseline(z_score=3.5), _contract()).severity == "high"
    assert apply_gates(_baseline(z_score=-3.5), _contract()).severity == "high"  # symmetric


def test_cold_start_suppresses_severity_but_keeps_zscore():
    result = apply_gates(_baseline(z_score=5.0, history_days=5), _contract(min_history_days=14))
    assert result.severity == "none"
    assert "cold_start" in result.flags
    assert result.z_score == 5.0  # raw observation preserved for audit


def test_low_volume_suppresses_severity():
    result = apply_gates(
        _baseline(z_score=5.0), _contract(min_volume_share=0.05), entity_share_of_total=0.01
    )
    assert result.severity == "none"
    assert "low_volume" in result.flags


def test_volume_gate_ignored_when_share_not_provided():
    result = apply_gates(_baseline(z_score=5.0), _contract(min_volume_share=0.05), entity_share_of_total=None)
    assert result.severity == "high"


def test_insufficient_history_short_circuits():
    baseline = BaselineResult(median=None, scaled_mad=None, z_score=None, history_days=0, sample_size=0)
    result = apply_gates(baseline, _contract())
    assert result.severity == "none"
    assert result.flags == ("insufficient_history",)
