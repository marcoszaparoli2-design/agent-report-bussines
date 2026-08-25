"""End-to-end orchestration.

dados -> metricas deterministicas -> deteccao -> scoring -> ranking ->
contexto estruturado -> LLM (opcional) -> report.

The LLM never computes a number: every number in the final report is
produced by the deterministic stages before curation ever runs.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.anomaly_detection.deviation_model import compute_baseline
from src.anomaly_detection.gates import apply_gates
from src.anomaly_detection.streak_tracker import compute_persistence
from src.config import (
    DetectionSensitivityConfig,
    SeasonalityCalendarConfig,
    load_detection_sensitivity,
    load_seasonality_calendar,
)
from src.context.explainability import SignalContext, build_signal_context
from src.context.knowledge_loader import load_knowledge
from src.curation.curator import curate
from src.curation.llm_provider import LLMProvider
from src.data.metric_schema import MetricContract, load_all_contracts
from src.data.sources.base import DataPoint, DataSource
from src.data.sources.fixture_source import FixtureDataSource
from src.observability.audit_log import AuditLog
from src.prioritization.impact_scoring import compute_impact, compute_relevance
from src.prioritization.priority_ranking import build_queues
from src.reporting.render import render_json, render_short_text


@dataclass(frozen=True)
class PipelineResult:
    json_report: dict
    text_report: str
    all_signals: tuple[SignalContext, ...]
    ranked_signals: tuple[SignalContext, ...]


def run_pipeline(
    as_of_date: date,
    metrics_dir: str | Path = "metrics",
    fixtures_dir: str | Path = "fixtures/metrics",
    config_dir: str | Path = "config",
    knowledge_dir: str | Path = "knowledge",
    audit_path: str | Path = ".audit/signals.jsonl",
    data_source: DataSource | None = None,
    llm_provider: LLMProvider | None = None,
) -> PipelineResult:
    config_dir = Path(config_dir)
    sensitivity = load_detection_sensitivity(config_dir / "detection_sensitivity.yaml")
    calendar = load_seasonality_calendar(config_dir / "seasonality_calendar.yaml")

    contracts = load_all_contracts(metrics_dir)
    source = data_source or FixtureDataSource(fixtures_dir)

    all_signals: list[SignalContext] = []
    for contract in contracts:
        all_signals.extend(_score_metric(contract, as_of_date, source, calendar, sensitivity))

    queues = build_queues(all_signals, sensitivity)

    knowledge_text = load_knowledge(knowledge_dir)
    curated = curate(list(queues.all_ranked), knowledge_text, llm_provider)

    json_report = render_json(curated, list(queues.all_ranked), as_of_date)
    text_report = render_short_text(curated)

    run_id = f"{as_of_date.isoformat()}-{uuid.uuid4().hex[:8]}"
    AuditLog(audit_path).record(all_signals, run_id=run_id)

    return PipelineResult(
        json_report=json_report,
        text_report=text_report,
        all_signals=tuple(all_signals),
        ranked_signals=queues.all_ranked,
    )


def _score_metric(
    contract: MetricContract,
    as_of_date: date,
    source: DataSource,
    calendar: SeasonalityCalendarConfig,
    sensitivity: DetectionSensitivityConfig,
) -> list[SignalContext]:
    points = source.fetch_series(contract.name, as_of_date)

    by_entity: dict[str, list[DataPoint]] = {}
    for point in points:
        by_entity.setdefault(point.entity, []).append(point)

    today_by_entity: dict[str, DataPoint | None] = {
        entity: next((p for p in series if p.metric_date == as_of_date), None)
        for entity, series in by_entity.items()
    }

    total_primary_volume = 0.0
    for today_point in today_by_entity.values():
        if today_point is None:
            continue
        total_primary_volume += today_point.volume if today_point.volume is not None else today_point.value

    signals: list[SignalContext] = []
    for entity, series in by_entity.items():
        today_point = today_by_entity[entity]
        if today_point is None:
            # No observation for today: nothing to score. A real pipeline
            # would still emit a "missing data" audit entry here; the MVP
            # simply skips it rather than crashing.
            continue

        baseline = compute_baseline(
            series,
            as_of_date,
            today_point.value,
            contract.window_days,
            calendar_exclusions=calendar.holidays,
        )

        entity_volume_today = today_point.volume if today_point.volume is not None else today_point.value
        entity_share = entity_volume_today / total_primary_volume if total_primary_volume else None

        gated = apply_gates(baseline, contract, entity_share_of_total=entity_share)
        persistence = compute_persistence(series, as_of_date, contract)

        delta_absolute = None if baseline.median is None else today_point.value - baseline.median
        impact = compute_impact(
            delta_absolute=delta_absolute or 0.0,
            method=contract.impact_method,
            entity_volume=entity_volume_today,
            total_primary_volume=total_primary_volume,
            sensitivity_coefficient=None,
        )

        confidence = 1.0 if not gated.flags else 0.3

        relevance = 0.0
        if gated.severity != "none" and gated.z_score is not None:
            relevance = compute_relevance(
                z_score=gated.z_score,
                severity_high_threshold=contract.severity.high,
                impact_share=impact.impact_share,
                consecutive_days_off=persistence.consecutive_days_off,
                confidence=confidence,
                sensitivity=contract.sensitivity,
                weights=sensitivity.priority_weights,
            )

        signal = build_signal_context(
            metric=contract.name,
            entity=entity,
            dimension=contract.dimension,
            as_of_date=as_of_date,
            current_value=today_point.value,
            baseline_value=baseline.median,
            z_score=gated.z_score,
            severity=gated.severity,
            bad_direction_sign=contract.bad_direction_sign(),
            impact_share=impact.impact_share,
            used_default_sensitivity=impact.used_default_sensitivity,
            consecutive_days_off=persistence.consecutive_days_off,
            trend=persistence.trend,
            relevance_score=relevance,
            confidence=confidence,
            flags=gated.flags,
            evidence_source=f"fixture:{contract.name}.csv",
        )
        signals.append(signal)

    return signals
