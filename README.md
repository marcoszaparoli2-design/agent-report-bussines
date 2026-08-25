# agent-report-bussines

A business intelligence curation agent: it collects metrics, detects
meaningful deviations, prioritizes them by business impact, attaches
explainable context, and generates a short, objective report for
stakeholders -- with or without an LLM.

Full architecture and design rationale: **[`CLEAN_ROOM_SPEC.md`](./CLEAN_ROOM_SPEC.md)**
(source of truth for this implementation). Deferred work: [`docs/roadmap/next-phases.md`](./docs/roadmap/next-phases.md).

## Pipeline

```
data -> deterministic metrics -> detection -> scoring -> ranking
-> structured context -> LLM (optional) -> report
```

Numbers, deltas, rankings, and inclusion/exclusion decisions are all
produced by deterministic code *before* anything reaches an LLM. The LLM
(if configured) only writes prose from numbers it's handed; a
guardrail rejects any narrative that introduces a number not present in
the structured context, and falls back to a deterministic report if it
does. The pipeline never leaves a reader with no report at all -- even with
zero LLM configured, `src/curation/fallback.py` produces one.

## Quick start

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; use .venv\Scripts\activate on cmd/PowerShell
pip install -r requirements-dev.txt

# generate the deterministic example fixtures (idempotent, no randomness)
python scripts/gen_fixtures.py

# run the pipeline once against the example fixtures
python scripts/run_pipeline.py --date 2024-03-10

# run the tests
pytest
```

`scripts/run_pipeline.py --output text|json|both` controls what gets printed.

## Project layout

```
src/
├── config.py                       # typed loader for config/*.yaml
├── pipeline.py                     # end-to-end orchestration
├── data/
│   ├── metric_schema.py            # metric contract (metrics/<name>/contract.yaml) loader
│   └── sources/                    # DataSource interface + FixtureDataSource
├── anomaly_detection/
│   ├── deviation_model.py          # median+MAD robust baseline, same-weekday, z-score
│   ├── gates.py                    # cold-start / low-volume / severity gates
│   └── streak_tracker.py           # consecutive-days-off + trend
├── prioritization/
│   ├── impact_scoring.py           # impact (deviation, not raw value) + relevance formula
│   └── priority_ranking.py         # negative/positive queues, top-N cut
├── context/
│   ├── explainability.py           # SignalContext: every number + evidence + reason
│   └── knowledge_loader.py         # injects knowledge/*.md into the curation prompt
├── curation/
│   ├── llm_provider.py             # LLMProvider interface (no vendor implementation ships)
│   ├── schema.py                   # anti-hallucination guardrail (number-matching)
│   ├── fallback.py                 # deterministic narrative, no LLM required
│   └── curator.py                  # orchestrates the single LLM call + guardrail + fallback
├── reporting/render.py             # structured output -> JSON / short text
└── observability/audit_log.py      # write-only log of every computed signal

metrics/<name>/{contract.yaml, query.sql}   # one pair per tracked metric
fixtures/metrics/<name>.csv                 # deterministic synthetic data for local runs
config/*.yaml                               # detection sensitivity, calendar, delivery channel
knowledge/*.md                              # business-context skeleton (fill in your own)
scripts/{run_pipeline.py, gen_fixtures.py}
tests/                                      # see "Tests" below
```

## Configuration

- `config/detection_sensitivity.yaml` -- how sensitive the detector/ranker
  is (severity thresholds live per-metric in `metrics/<name>/contract.yaml`;
  this file holds the *priority* weights and queue sizes). Never business
  baselines.
- `config/seasonality_calendar.yaml` -- calendar dates excluded from the
  baseline history window.
- `config/delivery_channels.yaml` -- which channel type and schedule to
  use; the actual secret is read from an environment variable named here
  (see `.env.example`), never hardcoded.

## Adding a metric

1. Create `metrics/<name>/contract.yaml` (see the two existing examples)
   and `metrics/<name>/query.sql` (a placeholder until a real warehouse
   adapter exists).
2. Add `fixtures/metrics/<name>.csv` with columns `date,entity,value[,volume]`
   for local development, or point a real `DataSource` implementation at it.
3. `pipeline.py` picks up any contract under `metrics/*/contract.yaml`
   automatically -- no other code change needed.

## Tests

```bash
pytest -v
```

46 tests covering: baseline/z-score math (including the relative floor and
same-weekday filtering), quality gates, persistence/trend, impact +
relevance scoring (including configurable weights), metric-contract
validation, the anti-hallucination guardrail, the deterministic fallback
(including incomplete-data signals), and two end-to-end pipeline runs
(one with a mock LLM that stays within the guardrail, one that hallucinates
and is caught).

## Design principles (see `CLEAN_ROOM_SPEC.md` for the full rationale)

- **Data before the LLM.** Every number in the final report is computed by
  deterministic code before curation ever runs.
- **No silent hallucination.** `curation/schema.py` extracts every number a
  narrative contains and rejects it if it can't be traced to the structured
  context; a rejected narrative falls back to the deterministic path.
- **Decoupled integrations.** Data sources, LLM providers, and delivery
  channels are all interfaces -- swap an adapter without touching detection,
  scoring, or curation.
- **Auditable by default.** Every computed signal, fired or not, is written
  to a write-only audit log for later calibration.
