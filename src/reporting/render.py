"""Pure rendering functions: structured output -> message blocks. No business logic here.

Two formats, per CLEAN_ROOM_SPEC.md section "Report":
  - JSON: full structured output, numbers + narrative + evidence.
  - short text: a compact briefing for chat channels (Slack/Teams/etc.),
    with a second, renderer-level item cap as a defensive line beyond
    whatever the curator already did.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from src.context.explainability import SignalContext
from src.curation.schema import CuratedReport


def render_json(
    report: CuratedReport,
    signals: list[SignalContext],
    as_of_date: date,
) -> dict:
    items_by_key = {f"{i.metric}|{i.entity}": i.text for i in report.items}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": as_of_date.isoformat(),
        "all_clear": len(signals) == 0,
        "source": report.source,
        "guardrail_violations": list(report.guardrail_violations),
        "overall_summary": report.overall_text,
        "signals": [
            {
                "metric": s.metric,
                "entity": s.entity,
                "dimension": s.dimension,
                "severity": s.severity,
                "current_value": s.current_value,
                "baseline_value": s.baseline_value,
                "delta_absolute": s.delta_absolute,
                "delta_relative": s.delta_relative,
                "z_score": s.z_score,
                "impact_share": s.impact_share,
                "relevance_score": s.relevance_score,
                "confidence": s.confidence,
                "consecutive_days_off": s.consecutive_days_off,
                "trend": s.trend,
                "priority_reason": s.priority_reason,
                "evidence": list(s.evidence),
                "flags": list(s.flags),
                "narrative_text": items_by_key.get(f"{s.metric}|{s.entity}", ""),
            }
            for s in signals
        ],
    }


def render_short_text(report: CuratedReport, max_items: int = 5) -> str:
    lines = ["Business Report", "", report.overall_text]

    shown_items = report.items[:max_items]
    hidden_count = len(report.items) - len(shown_items)

    for idx, item in enumerate(shown_items, start=1):
        title = item.metric.replace("_", " ").title()
        lines.append("")
        lines.append(f"{idx}. {title} ({item.entity})")
        lines.append(f"- {item.text}")

    if hidden_count > 0:
        lines.append("")
        lines.append(f"+ {hidden_count} outro(s) sinal(is) nao exibido(s) neste resumo.")

    return "\n".join(lines)
