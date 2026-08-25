"""Builds the structured, explainable context object for one signal.

This is the ONLY thing the curation layer (and, eventually, an LLM) ever
sees. It carries every number pre-computed by deterministic code, plus a
code-written priority reason and evidence trail -- so nothing downstream
ever needs to (or is allowed to) invent a number.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone


@dataclass(frozen=True)
class SignalContext:
    metric: str
    entity: str
    dimension: str
    as_of_date: date
    current_value: float
    baseline_value: float | None
    delta_absolute: float | None
    delta_relative: float | None
    z_score: float | None
    severity: str  # "none" | "watch" | "high"
    is_bad_direction: bool
    impact_share: float
    used_default_sensitivity: bool
    consecutive_days_off: int
    trend: dict[int, str]
    relevance_score: float
    confidence: float
    flags: tuple[str, ...]
    priority_reason: str
    evidence: tuple[dict, ...]
    generated_at: str

    def allowed_numbers(self, tolerance_rounding: tuple[int, ...] = (0, 1, 2, 3)) -> set[float]:
        """Every number a narrative describing this signal is allowed to use.

        Includes the raw values at several roundings (an LLM may write "12.3%"
        or "12%") plus percent-scaled forms of ratios. Used by the guardrail
        in curation/schema.py to reject any number not traceable to this signal.
        """
        candidates: set[float] = set()

        def add(value: float | None, allow_percent: bool = False, allow_unsigned: bool = False) -> None:
            if value is None:
                return
            for nd in tolerance_rounding:
                candidates.add(round(value, nd))
                if allow_unsigned:
                    candidates.add(round(abs(value), nd))
            if allow_percent:
                for nd in tolerance_rounding:
                    candidates.add(round(value * 100, nd))
                    if allow_unsigned:
                        candidates.add(round(abs(value) * 100, nd))

        add(self.current_value)
        add(self.baseline_value)
        add(self.delta_absolute, allow_unsigned=True)
        add(self.z_score, allow_unsigned=True)
        add(self.impact_share, allow_percent=True, allow_unsigned=True)
        add(self.delta_relative, allow_percent=True, allow_unsigned=True)
        add(float(self.consecutive_days_off))
        return candidates


def build_signal_context(
    *,
    metric: str,
    entity: str,
    dimension: str,
    as_of_date: date,
    current_value: float,
    baseline_value: float | None,
    z_score: float | None,
    severity: str,
    bad_direction_sign: int,
    impact_share: float,
    used_default_sensitivity: bool,
    consecutive_days_off: int,
    trend: dict[int, str],
    relevance_score: float,
    confidence: float,
    flags: tuple[str, ...],
    evidence_source: str,
) -> SignalContext:
    delta_absolute = None if baseline_value is None else current_value - baseline_value
    delta_relative = (
        None if baseline_value in (None, 0) else delta_absolute / baseline_value
    )
    is_bad_direction = delta_absolute is not None and (delta_absolute * bad_direction_sign) > 0

    priority_reason = _build_priority_reason(
        severity=severity,
        z_score=z_score,
        consecutive_days_off=consecutive_days_off,
        impact_share=impact_share,
        flags=flags,
    )

    generated_at = datetime.now(timezone.utc).isoformat()
    evidence = (
        {
            "source": evidence_source,
            "metric": metric,
            "entity": entity,
            "as_of": as_of_date.isoformat(),
            "current_value": current_value,
        },
    )

    return SignalContext(
        metric=metric,
        entity=entity,
        dimension=dimension,
        as_of_date=as_of_date,
        current_value=current_value,
        baseline_value=baseline_value,
        delta_absolute=delta_absolute,
        delta_relative=delta_relative,
        z_score=z_score,
        severity=severity,
        is_bad_direction=is_bad_direction,
        impact_share=impact_share,
        used_default_sensitivity=used_default_sensitivity,
        consecutive_days_off=consecutive_days_off,
        trend=trend,
        relevance_score=relevance_score,
        confidence=confidence,
        flags=flags,
        priority_reason=priority_reason,
        evidence=evidence,
        generated_at=generated_at,
    )


def _build_priority_reason(
    *,
    severity: str,
    z_score: float | None,
    consecutive_days_off: int,
    impact_share: float,
    flags: tuple[str, ...],
) -> str:
    if flags:
        return f"Sinal suprimido por: {', '.join(flags)}."
    if severity == "none" or z_score is None:
        return "Dentro do comportamento esperado; sem desvio relevante."

    parts = [f"Desvio de {z_score:.1f} desvios-padrao robustos em relacao ao baseline historico ({severity})."]
    if consecutive_days_off >= 2:
        parts.append(f"Padrao sustentado ha {consecutive_days_off} periodos consecutivos.")
    parts.append(f"Impacto estimado de {abs(impact_share) * 100:.1f}% sobre o volume total do dia.")
    return " ".join(parts)
