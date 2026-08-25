"""Decoupled LLM provider interface.

No implementation ships in the MVP -- the pipeline works entirely without one
(see fallback.py). Plug in a real provider (Anthropic, OpenAI, a local model,
anything) by implementing this interface; nothing else in the codebase
depends on a specific vendor.

The provider is asked ONLY to produce narrative text from numbers it is
handed -- never to compute, recompute, or reorder anything.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.context.explainability import SignalContext


class LLMProvider(ABC):
    @abstractmethod
    def generate_narrative(self, system_prompt: str, signals: list[SignalContext]) -> dict[str, str]:
        """Return narrative text for the report.

        The returned dict must contain:
          - "overall": a short overall-summary string
          - one entry per signal, keyed by f"{signal.metric}|{signal.entity}"

        Implementations must never introduce a number that isn't present in
        the corresponding SignalContext -- the curator validates this and
        falls back to a deterministic report if it isn't respected.
        """
        raise NotImplementedError
