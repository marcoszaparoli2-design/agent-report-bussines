"""Write-only audit log.

Captures every computed signal -- severity or not -- so a human can later
ask "why didn't this fire yesterday" or measure the real false-positive rate.
Architecturally separate from any delivery/history table: no pipeline stage
ever reads this back.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.context.explainability import SignalContext


class AuditLog:
    def __init__(self, path: str | Path):
        self._path = Path(path)

    def record(self, signals: list[SignalContext], run_id: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            for signal in signals:
                entry = asdict(signal)
                entry["as_of_date"] = signal.as_of_date.isoformat()
                entry["run_id"] = run_id
                fh.write(json.dumps(entry, default=str) + "\n")
