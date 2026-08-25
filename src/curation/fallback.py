"""Deterministic fallback narrative generator.

If the curation call fails, is unavailable, or produces a number that can't
be traced to the structured context, this is what runs instead. The reader
never gets no briefing at all -- and this path is built and tested before
any LLM path, not after.
"""
from __future__ import annotations

from src.context.explainability import SignalContext
from src.curation.schema import CuratedItem, CuratedReport


def render_fallback(signals: list[SignalContext]) -> CuratedReport:
    if not signals:
        return CuratedReport(
            overall_text="Nenhuma mudanca relevante identificada hoje.",
            items=(),
            source="fallback",
            guardrail_violations=(),
        )

    overall_text = f"{len(signals)} mudanca(s) relevante(s) identificada(s)."

    items = []
    for signal in signals:
        direction_word = _direction_word(signal)
        lines = [f"{direction_word} versus baseline ({signal.severity})."]
        if signal.consecutive_days_off >= 2:
            lines.append(f"Persistencia observada nos ultimos {signal.consecutive_days_off} periodos.")
        lines.append(f"Impacto estimado de {abs(signal.impact_share) * 100:.1f}% sobre o volume total do dia.")
        if signal.used_default_sensitivity:
            lines.append("Sensibilidade de negocio nao configurada para esta entidade; usando peso padrao.")
        items.append(CuratedItem(metric=signal.metric, entity=signal.entity, text=" ".join(lines)))

    return CuratedReport(overall_text=overall_text, items=tuple(items), source="fallback", guardrail_violations=())


def _direction_word(signal: SignalContext) -> str:
    if signal.delta_absolute is None:
        return "Mudanca"
    if signal.is_bad_direction:
        return "Queda relevante" if signal.delta_absolute < 0 else "Alta relevante (direcao desfavoravel)"
    return "Alta relevante" if signal.delta_absolute > 0 else "Queda relevante (direcao favoravel)"
