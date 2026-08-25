from datetime import date

from src.context.explainability import build_signal_context
from src.curation.schema import extract_numbers, find_hallucinated_numbers, validate_item_text, validate_overall_text


def _signal(**overrides):
    defaults = dict(
        metric="revenue",
        entity="region_south",
        dimension="region",
        as_of_date=date(2024, 3, 10),
        current_value=17825.0,
        baseline_value=10600.0,
        z_score=13.632075471698114,
        severity="high",
        bad_direction_sign=-1,
        impact_share=0.16792562463683905,
        used_default_sensitivity=False,
        consecutive_days_off=0,
        trend={},
        relevance_score=1.0,
        confidence=1.0,
        flags=(),
        evidence_source="fixture:revenue.csv",
    )
    defaults.update(overrides)
    return build_signal_context(**defaults)


def test_narrative_using_only_context_numbers_passes():
    signal = _signal()
    text = "Alta relevante de 68.2% versus baseline, impacto de 16.8% sobre o volume total."
    assert validate_item_text(text, signal) == []


def test_narrative_with_fabricated_number_is_rejected():
    signal = _signal()
    text = "Alta relevante, impacto de 42.0% sobre o volume total."
    violations = validate_item_text(text, signal)
    assert 42.0 in violations


def test_ordered_list_markers_are_not_treated_as_numbers():
    assert extract_numbers("1. Conversion Rate\n2. Revenue") == []


def test_hallucinated_number_detection_respects_tolerance():
    allowed = {100.0}
    assert find_hallucinated_numbers("valor de 100.02", allowed, tolerance=0.05) == []
    assert find_hallucinated_numbers("valor de 100.2", allowed, tolerance=0.05) == [100.2]


def test_overall_text_may_state_the_signal_count():
    assert validate_overall_text("3 mudancas relevantes identificadas.", signal_count=3) == []


def test_overall_text_rejects_a_fabricated_count():
    violations = validate_overall_text("9 mudancas relevantes identificadas.", signal_count=3)
    assert 9.0 in violations


def test_missing_baseline_signal_still_has_no_hallucination_risk():
    signal = _signal(baseline_value=None, z_score=None, severity="none", impact_share=0.0, flags=("insufficient_history",))
    text = "Dados insuficientes para avaliar esta entidade."
    assert validate_item_text(text, signal) == []
