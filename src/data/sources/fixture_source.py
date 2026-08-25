"""Reads deterministic CSV fixtures through the same interface a real warehouse adapter uses.

A future adapter (e.g. BigQuery, Postgres) implements the same DataSource
interface and can replace this one without touching any other module.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from .base import DataPoint, DataSource


class FixtureDataSource(DataSource):
    """CSV columns: date,entity,value[,volume]. One file per metric: <fixtures_dir>/<metric_name>.csv"""

    def __init__(self, fixtures_dir: str | Path):
        self._fixtures_dir = Path(fixtures_dir)

    def fetch_series(self, metric_name: str, as_of_date: date) -> list[DataPoint]:
        path = self._fixtures_dir / f"{metric_name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"no fixture found for metric '{metric_name}' at {path}")

        points: list[DataPoint] = []
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                row_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
                if row_date > as_of_date:
                    continue
                volume_raw = row.get("volume")
                volume = float(volume_raw) if volume_raw not in (None, "") else None
                points.append(
                    DataPoint(
                        metric_date=row_date,
                        entity=row["entity"],
                        value=float(row["value"]),
                        volume=volume,
                    )
                )
        return points
