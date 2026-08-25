"""Abstract interface every data source (warehouse, API, fixture) must implement."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DataPoint:
    """One observation of a metric for one entity on one date."""

    metric_date: date
    entity: str
    value: float
    volume: float | None = None  # optional exposure/weight, used by weighted impact methods


class DataSource(ABC):
    """Reads the full available history for a metric. No business logic lives here."""

    @abstractmethod
    def fetch_series(self, metric_name: str, as_of_date: date) -> list[DataPoint]:
        """Return every historical DataPoint available for this metric up to and including as_of_date."""
        raise NotImplementedError
