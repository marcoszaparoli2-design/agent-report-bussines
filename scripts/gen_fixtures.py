#!/usr/bin/env python3
"""Deterministic synthetic fixture generator.

No randomness, no external calls -- running this twice produces byte-identical
CSVs. Generates ~10 weeks of daily history for two example metrics
(conversion_rate, revenue) across a few generic entities, with one deliberate
anomaly injected on AS_OF_DATE per metric so the pipeline has something to
detect out of the box.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

AS_OF_DATE = date(2024, 3, 10)
HISTORY_DAYS = 70
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "metrics"


def _weekday_wave(offset: int, amplitude: float) -> float:
    """Small deterministic same-weekday oscillation so the baseline has something to normalize."""
    return amplitude * ((offset % 7) - 3) / 3


def generate_conversion_rate() -> None:
    entities = {
        "segment_a": {"base": 0.115, "volume": 4200},
        "segment_b": {"base": 0.102, "volume": 3100},
        "segment_c": {"base": 0.128, "volume": 2600},
    }
    rows = []
    for offset in range(HISTORY_DAYS, -1, -1):
        current_date = AS_OF_DATE - timedelta(days=offset)
        for entity, params in entities.items():
            value = params["base"] + _weekday_wave(offset, 0.006)
            if entity == "segment_b" and current_date == AS_OF_DATE:
                value = params["base"] * 0.62  # deliberate acute drop, today only
            rows.append((current_date.isoformat(), entity, round(value, 4), params["volume"]))
    _write_csv("conversion_rate.csv", rows)


def generate_revenue() -> None:
    entities = {
        "region_north": {"base": 18000.0},
        "region_south": {"base": 11500.0},
        "region_east": {"base": 9000.0},
    }
    rows = []
    for offset in range(HISTORY_DAYS, -1, -1):
        current_date = AS_OF_DATE - timedelta(days=offset)
        for entity, params in entities.items():
            value = params["base"] + _weekday_wave(offset, 900)
            if entity == "region_south" and current_date == AS_OF_DATE:
                value = params["base"] * 1.55  # deliberate acute rise, today only
            rows.append((current_date.isoformat(), entity, round(value, 2), ""))
    _write_csv("revenue.csv", rows)


def _write_csv(filename: str, rows: list[tuple]) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURES_DIR / filename
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "entity", "value", "volume"])
        writer.writerows(rows)


if __name__ == "__main__":
    generate_conversion_rate()
    generate_revenue()
    print(f"Fixtures written to {FIXTURES_DIR}")
