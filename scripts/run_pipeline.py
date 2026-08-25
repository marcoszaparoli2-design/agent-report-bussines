#!/usr/bin/env python3
"""CLI entry point: run the full pipeline once and print the report.

Usage:
    python scripts/run_pipeline.py --date 2024-03-10
    python scripts/run_pipeline.py --date 2024-03-10 --output json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import run_pipeline  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run_pipeline")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the business intelligence curation pipeline once.")
    parser.add_argument("--date", type=str, default=None, help="As-of date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--metrics-dir", type=str, default="metrics")
    parser.add_argument("--fixtures-dir", type=str, default="fixtures/metrics")
    parser.add_argument("--config-dir", type=str, default="config")
    parser.add_argument("--knowledge-dir", type=str, default="knowledge")
    parser.add_argument("--audit-path", type=str, default=".audit/signals.jsonl")
    parser.add_argument("--output", choices=["json", "text", "both"], default="both")
    args = parser.parse_args()

    as_of_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    logger.info("Running pipeline for as_of_date=%s", as_of_date.isoformat())

    result = run_pipeline(
        as_of_date=as_of_date,
        metrics_dir=args.metrics_dir,
        fixtures_dir=args.fixtures_dir,
        config_dir=args.config_dir,
        knowledge_dir=args.knowledge_dir,
        audit_path=args.audit_path,
    )

    logger.info(
        "Scored %d signal(s), %d ranked into the report (source=%s)",
        len(result.all_signals),
        len(result.ranked_signals),
        result.json_report["source"],
    )

    if args.output in ("text", "both"):
        print(result.text_report)
    if args.output == "both":
        print()
    if args.output in ("json", "both"):
        print(json.dumps(result.json_report, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
