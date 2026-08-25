"""Orchestrates the single curation call.

dados -> metricas deterministicas -> deteccao -> scoring -> ranking ->
contexto estruturado -> [ESTE MODULO] -> report.

Everything upstream is deterministic code. The LLM (if configured) receives
a small, pre-ranked, pre-deduplicated payload and is only ever asked to
write prose -- it never computes, recomputes, or reorders anything. Its
output is validated against the guardrail before being trusted; any
violation (or any failure at all) falls back to the deterministic path.
"""
from __future__ import annotations

from src.context.explainability import SignalContext
from src.curation.fallback import render_fallback
from src.curation.llm_provider import LLMProvider
from src.curation.schema import CuratedItem, CuratedReport, validate_item_text, validate_overall_text


def curate(
    signals: list[SignalContext],
    knowledge_text: str,
    llm_provider: LLMProvider | None = None,
) -> CuratedReport:
    if llm_provider is None:
        return render_fallback(signals)

    system_prompt = _build_system_prompt(knowledge_text)
    try:
        raw = llm_provider.generate_narrative(system_prompt, signals)
    except Exception:
        return render_fallback(signals)

    violations: list[str] = []

    overall_text = raw.get("overall", "")
    overall_violations = validate_overall_text(overall_text, signal_count=len(signals))
    if overall_violations:
        violations.append(f"overall: hallucinated numbers {overall_violations}")

    items: list[CuratedItem] = []
    for signal in signals:
        key = f"{signal.metric}|{signal.entity}"
        text = raw.get(key)
        if text is None:
            violations.append(f"{key}: missing narrative")
            continue
        item_violations = validate_item_text(text, signal)
        if item_violations:
            violations.append(f"{key}: hallucinated numbers {item_violations}")
            continue
        items.append(CuratedItem(metric=signal.metric, entity=signal.entity, text=text))

    if violations:
        fallback = render_fallback(signals)
        return CuratedReport(
            overall_text=fallback.overall_text,
            items=fallback.items,
            source="fallback_on_guardrail",
            guardrail_violations=tuple(violations),
        )

    return CuratedReport(overall_text=overall_text, items=tuple(items), source="llm", guardrail_violations=())


def _build_system_prompt(knowledge_text: str) -> str:
    rules = (
        "Voce escreve um briefing curto de negocio a partir de sinais ja "
        "calculados e ranqueados por codigo determinístico.\n"
        "Regras obrigatorias:\n"
        "- Nunca invente ou recalcule um numero; use apenas os numeros fornecidos.\n"
        "- Nunca reordene os sinais; a ordem ja foi decidida por codigo.\n"
        "- Mescle sinais correlacionados quando fizer sentido narrativo.\n"
        "- Seja factual, sem alarmismo, sem recomendacao de acao.\n"
    )
    if knowledge_text:
        return f"{rules}\nContexto de negocio:\n{knowledge_text}"
    return rules
