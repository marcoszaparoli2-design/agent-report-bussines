from datetime import date

from src.context.explainability import build_signal_context
from src.curation.fallback import render_fallback
from src.curation.schema import validate_item_text, validate_overall_text


def test_fallback_with_no_signals_still_produces_a_report():
    report = render_fallback([])
    assert report.source == "fallback"
    assert "Nenhuma mudanca relevante" in report.overall_text
    assert report.items == ()


def test_fallback_handles_a_signal_with_missing_baseline_without_crashing():
    signal = build_signal_context(
        metric="revenue",
        entity="new_region",
        dimension="region",
        as_of_date=date(2024, 3, 10),
        current_value=500.0,
        baseline_value=None,
        z_score=None,
        severity="none",
        bad_direction_sign=-1,
        impact_share=0.0,
        used_default_sensitivity=False,
        consecutive_days_off=0,
        trend={},
        relevance_score=0.0,
        confidence=0.3,
        flags=("insufficient_history",),
        evidence_source="fixture:revenue.csv",
    )

    report = render_fallback([signal])

    assert len(report.items) == 1
    assert report.items[0].entity == "new_region"


def test_fallback_output_always_passes_its_own_guardrail():
    signal = build_signal_context(
        metric="revenue",
        entity="region_south",
        dimension="region",
        as_of_date=date(2024, 3, 10),
        current_value=17825.0,
        baseline_value=10600.0,
        z_score=13.63,
        severity="high",
        bad_direction_sign=-1,
        impact_share=0.168,
        used_default_sensitivity=False,
        consecutive_days_off=3,
        trend={},
        relevance_score=1.0,
        confidence=1.0,
        flags=(),
        evidence_source="fixture:revenue.csv",
    )

    report = render_fallback([signal])

    assert validate_item_text(report.items[0].text, signal) == []
    assert validate_overall_text(report.overall_text, signal_count=1) == []
