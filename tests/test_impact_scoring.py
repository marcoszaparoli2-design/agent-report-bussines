from src.config import PriorityWeights
from src.prioritization.impact_scoring import compute_impact, compute_relevance


def test_direct_delta_impact_and_share():
    result = compute_impact(
        delta_absolute=100.0, method="direct_delta", entity_volume=None, total_primary_volume=1000.0
    )
    assert result.impact_value == 100.0
    assert result.impact_share == 0.1
    assert result.used_default_sensitivity is False


def test_exposure_weighted_rate_impact():
    result = compute_impact(
        delta_absolute=0.01, method="exposure_weighted_rate", entity_volume=500.0, total_primary_volume=1000.0
    )
    assert result.impact_value == 5.0
    assert result.impact_share == 0.005


def test_business_sensitivity_weighted_uses_default_and_flags_it():
    result = compute_impact(
        delta_absolute=0.01,
        method="business_sensitivity_weighted",
        entity_volume=500.0,
        total_primary_volume=1000.0,
        sensitivity_coefficient=None,
    )
    assert result.used_default_sensitivity is True
    assert result.impact_value == 0.01 * 500.0 * 1.0


def test_business_sensitivity_weighted_uses_provided_coefficient():
    result = compute_impact(
        delta_absolute=0.01,
        method="business_sensitivity_weighted",
        entity_volume=500.0,
        total_primary_volume=1000.0,
        sensitivity_coefficient=3.0,
    )
    assert result.used_default_sensitivity is False
    assert result.impact_value == 0.01 * 500.0 * 3.0


def test_impact_share_is_zero_without_a_total_reference():
    result = compute_impact(delta_absolute=100.0, method="direct_delta", entity_volume=None, total_primary_volume=None)
    assert result.impact_share == 0.0


def test_relevance_increases_with_persistence():
    weights = PriorityWeights()
    base = compute_relevance(
        z_score=2.0,
        severity_high_threshold=3.0,
        impact_share=0.1,
        consecutive_days_off=0,
        confidence=1.0,
        sensitivity=1.0,
        weights=weights,
    )
    with_persistence = compute_relevance(
        z_score=2.0,
        severity_high_threshold=3.0,
        impact_share=0.1,
        consecutive_days_off=10,
        confidence=1.0,
        sensitivity=1.0,
        weights=weights,
    )
    assert with_persistence > base


def test_relevance_weight_of_zero_neutralizes_that_factor():
    weights = PriorityWeights(magnitude=1.0, impact=0.0, persistence=1.0, confidence=1.0)
    result = compute_relevance(
        z_score=2.0,
        severity_high_threshold=3.0,
        impact_share=0.5,
        consecutive_days_off=0,
        confidence=1.0,
        sensitivity=1.0,
        weights=weights,
    )
    assert result == 0.0


def test_relevance_is_insensitive_to_impact_direction():
    weights = PriorityWeights()
    negative_impact = compute_relevance(
        z_score=2.0, severity_high_threshold=3.0, impact_share=-0.2, consecutive_days_off=0,
        confidence=1.0, sensitivity=1.0, weights=weights,
    )
    positive_impact = compute_relevance(
        z_score=2.0, severity_high_threshold=3.0, impact_share=0.2, consecutive_days_off=0,
        confidence=1.0, sensitivity=1.0, weights=weights,
    )
    assert negative_impact == positive_impact
