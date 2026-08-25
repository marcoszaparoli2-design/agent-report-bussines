from datetime import date, timedelta

from src.context.explainability import SignalContext
from src.curation.llm_provider import LLMProvider
from src.pipeline import run_pipeline

AS_OF_DATE = date(2024, 3, 10)


def test_pipeline_end_to_end_with_fixtures(tmp_path):
    audit_path = tmp_path / "signals.jsonl"

    result = run_pipeline(as_of_date=AS_OF_DATE, audit_path=str(audit_path))

    # 3 entities x 2 metrics were scored, regardless of whether they fired
    assert len(result.all_signals) == 6

    # only the two deliberately-injected anomalies (see scripts/gen_fixtures.py) rank
    assert len(result.ranked_signals) == 2
    flagged = {(s.metric, s.entity) for s in result.ranked_signals}
    assert flagged == {("revenue", "region_south"), ("conversion_rate", "segment_b")}

    assert result.json_report["all_clear"] is False
    assert result.json_report["source"] == "fallback"
    assert result.json_report["guardrail_violations"] == []
    assert "Business Report" in result.text_report

    assert audit_path.exists()
    assert len(audit_path.read_text(encoding="utf-8").splitlines()) == 6


def test_pipeline_all_clear_when_no_signal_fires(tmp_path):
    audit_path = tmp_path / "signals.jsonl"
    quiet_date = AS_OF_DATE - timedelta(days=7)  # a non-anomalous day in the fixture

    result = run_pipeline(as_of_date=quiet_date, audit_path=str(audit_path))

    assert len(result.ranked_signals) == 0
    assert result.json_report["all_clear"] is True
    assert "Nenhuma mudanca relevante" in result.text_report


class _EchoLLMProvider(LLMProvider):
    """Writes narrative text using only numbers already present in the context -- should be trusted."""

    def generate_narrative(self, system_prompt: str, signals: list[SignalContext]) -> dict[str, str]:
        result = {"overall": f"{len(signals)} mudanca(s) relevante(s)."}
        for signal in signals:
            result[f"{signal.metric}|{signal.entity}"] = (
                f"Desvio de {abs(signal.z_score):.1f} sigma, "
                f"impacto de {abs(signal.impact_share) * 100:.1f}% sobre o volume total."
            )
        return result


class _HallucinatingLLMProvider(LLMProvider):
    """Fabricates a number that isn't in the context -- must trigger the fallback."""

    def generate_narrative(self, system_prompt: str, signals: list[SignalContext]) -> dict[str, str]:
        result = {"overall": f"{len(signals)} mudanca(s) relevante(s)."}
        for signal in signals:
            result[f"{signal.metric}|{signal.entity}"] = "Impacto de 999.9% fora de qualquer padrao conhecido."
        return result


def test_pipeline_trusts_llm_output_that_passes_the_guardrail(tmp_path):
    audit_path = tmp_path / "signals.jsonl"

    result = run_pipeline(as_of_date=AS_OF_DATE, audit_path=str(audit_path), llm_provider=_EchoLLMProvider())

    assert result.json_report["source"] == "llm"
    assert result.json_report["guardrail_violations"] == []


def test_pipeline_falls_back_when_llm_hallucinates_a_number(tmp_path):
    audit_path = tmp_path / "signals.jsonl"

    result = run_pipeline(
        as_of_date=AS_OF_DATE, audit_path=str(audit_path), llm_provider=_HallucinatingLLMProvider()
    )

    assert result.json_report["source"] == "fallback_on_guardrail"
    assert result.json_report["guardrail_violations"]
    # the numbers the reader actually sees still come from the deterministic fallback
    assert "999.9" not in result.text_report
