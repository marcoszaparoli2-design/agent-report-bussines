"""Loads config/*.yaml into typed objects.

These files hold detection-sensitivity knobs (how sensitive the detector is)
-- never business baselines (what's "normal" for a metric). That distinction
is deliberate: see CLEAN_ROOM_SPEC.md section 6.15.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml


@dataclass(frozen=True)
class PriorityWeights:
    magnitude: float = 1.0
    impact: float = 1.0
    persistence: float = 1.0
    confidence: float = 1.0


@dataclass(frozen=True)
class DetectionSensitivityConfig:
    priority_weights: PriorityWeights
    queue_top_n_negative: int
    queue_top_n_positive: int
    persistence_milestones_days: tuple[int, ...]


@dataclass(frozen=True)
class SeasonalityCalendarConfig:
    holidays: frozenset[date]
    atypical_periods: tuple[tuple[date, date], ...]

    def is_excluded(self, day: date) -> bool:
        if day in self.holidays:
            return True
        return any(start <= day <= end for start, end in self.atypical_periods)


@dataclass(frozen=True)
class DeliveryChannelsConfig:
    default_channel_type: str
    webhook_env_var: str | None
    schedule_time: str
    schedule_timezone: str


def load_detection_sensitivity(path: str | Path) -> DetectionSensitivityConfig:
    raw = _read_yaml(path)
    weights_raw = raw.get("priority_weights", {})
    weights = PriorityWeights(
        magnitude=float(weights_raw.get("magnitude", 1.0)),
        impact=float(weights_raw.get("impact", 1.0)),
        persistence=float(weights_raw.get("persistence", 1.0)),
        confidence=float(weights_raw.get("confidence", 1.0)),
    )
    queues_raw = raw.get("queues", {})
    return DetectionSensitivityConfig(
        priority_weights=weights,
        queue_top_n_negative=int(queues_raw.get("top_n_negative", 5)),
        queue_top_n_positive=int(queues_raw.get("top_n_positive", 3)),
        persistence_milestones_days=tuple(raw.get("persistence", {}).get("milestones_days", [7, 15, 30])),
    )


def load_seasonality_calendar(path: str | Path) -> SeasonalityCalendarConfig:
    raw = _read_yaml(path)
    holidays = frozenset(_parse_date(d) for d in raw.get("holidays", []))
    atypical = tuple(
        (_parse_date(p["start"]), _parse_date(p["end"])) for p in raw.get("atypical_periods", [])
    )
    return SeasonalityCalendarConfig(holidays=holidays, atypical_periods=atypical)


def load_delivery_channels(path: str | Path) -> DeliveryChannelsConfig:
    raw = _read_yaml(path)
    default_channel = raw.get("channels", {}).get("default", {})
    schedule = raw.get("schedule", {})
    return DeliveryChannelsConfig(
        default_channel_type=default_channel.get("type", "none"),
        webhook_env_var=default_channel.get("webhook_env_var"),
        schedule_time=schedule.get("time", "07:00"),
        schedule_timezone=schedule.get("timezone", "UTC"),
    )


def _read_yaml(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()
