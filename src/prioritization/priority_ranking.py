"""Builds and cuts the final priority queues that feed curation.

Separate queues per direction (instead of one blended score) so an acute
negative event never crowds a positive signal out of the message.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.config import DetectionSensitivityConfig
from src.context.explainability import SignalContext


@dataclass(frozen=True)
class Queues:
    negative: tuple[SignalContext, ...]
    positive: tuple[SignalContext, ...]
    all_ranked: tuple[SignalContext, ...]


def build_queues(signals: list[SignalContext], config: DetectionSensitivityConfig) -> Queues:
    active = [s for s in signals if s.severity != "none"]

    negative = sorted(
        (s for s in active if s.is_bad_direction),
        key=lambda s: s.relevance_score,
        reverse=True,
    )[: config.queue_top_n_negative]

    positive = sorted(
        (s for s in active if not s.is_bad_direction),
        key=lambda s: s.relevance_score,
        reverse=True,
    )[: config.queue_top_n_positive]

    all_ranked = sorted(active, key=lambda s: s.relevance_score, reverse=True)

    return Queues(negative=tuple(negative), positive=tuple(positive), all_ranked=tuple(all_ranked))
