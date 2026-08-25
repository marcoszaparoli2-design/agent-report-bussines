"""Structured report shape + the anti-hallucination guardrail.

The agent may only mention numbers present in the structured context it was
handed. This module extracts every number from a piece of narrative text and
rejects it if any number can't be traced back to the signal (or the overall
report) it describes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.context.explainability import SignalContext

_LIST_MARKER = re.compile(r"(?m)^\s*\d+\.\s+")
_NUMBER_PATTERN = re.compile(r"-?\d[\d,]*\.?\d*")


@dataclass(frozen=True)
class CuratedItem:
    metric: str
    entity: str
    text: str


@dataclass(frozen=True)
class CuratedReport:
    overall_text: str
    items: tuple[CuratedItem, ...]
    source: str  # "llm" | "fallback"
    guardrail_violations: tuple[str, ...]


def extract_numbers(text: str) -> list[float]:
    """Numeric tokens in text, ignoring markdown ordered-list markers ("1. ")."""
    cleaned = _LIST_MARKER.sub("", text)
    numbers = []
    for match in _NUMBER_PATTERN.finditer(cleaned):
        raw = match.group().replace(",", "")
        try:
            numbers.append(float(raw))
        except ValueError:
            continue
    return numbers


def find_hallucinated_numbers(text: str, allowed_numbers: set[float], tolerance: float = 0.05) -> list[float]:
    """Numbers present in text that cannot be matched (within tolerance) to allowed_numbers."""
    violations = []
    for n in extract_numbers(text):
        if not any(abs(n - a) <= tolerance for a in allowed_numbers):
            violations.append(n)
    return violations


def validate_item_text(text: str, signal: SignalContext, tolerance: float = 0.05) -> list[float]:
    return find_hallucinated_numbers(text, signal.allowed_numbers(), tolerance=tolerance)


def validate_overall_text(text: str, signal_count: int, tolerance: float = 0.5) -> list[float]:
    allowed = {float(signal_count), 0.0, 1.0}
    return find_hallucinated_numbers(text, allowed, tolerance=tolerance)
