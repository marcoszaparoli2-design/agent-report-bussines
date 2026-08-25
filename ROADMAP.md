# Roadmap

**Current status:** `v0.1 MVP / reference implementation`

This project is currently a **reference implementation and architecture
plan** for a business intelligence curation agent. It runs entirely against
local synthetic fixtures (`fixtures/metrics/`), has no connection to any
corporate data source, warehouse, LLM vendor, or delivery channel, and is
not deployed anywhere. See [`CLEAN_ROOM_SPEC.md`](./CLEAN_ROOM_SPEC.md) for
the full architecture and [`README.md`](./README.md) for how to run it.

The phases below extend the MVP in the order that keeps every step
demonstrable on its own, without any phase depending on business data that
doesn't exist yet.

---

## 1. Real Data Adapter

**Objective:** replace the fixture-only `FixtureDataSource` with at least
one adapter that reads from a real data warehouse, without changing any
downstream module.

**Key deliverables:**
- A `DataSource` implementation for a real backend (BigQuery, PostgreSQL,
  or similar), returning the same `DataPoint` shape the fixtures already
  produce.
- Secure credential configuration (environment variables / secret manager
  -- never committed, never hardcoded).
- A schema and data-quality validation step (required columns present,
  types correct, no unexpected nulls) before data reaches detection.

**Done when:** the pipeline runs unmodified end-to-end against the real
adapter for at least one metric, producing the same report shape it
produces today against fixtures.

## 2. Delivery Integrations

**Objective:** actually deliver the report somewhere, instead of only
printing it.

**Key deliverables:**
- A `DeliveryChannel` interface (mirroring the existing `DataSource` /
  `LLMProvider` decoupling pattern) with a first implementation for Slack.
- A second implementation (Teams or another channel) to prove the interface
  generalizes, not just the first channel's happy path.
- Delivery idempotency (a rerun for the same date/channel never
  double-posts), backed by a persisted history.

**Done when:** a report reaches a real channel exactly once per run, and
`config/delivery_channels.yaml` selects which adapter runs without code
changes.

## 3. LLM Provider

**Objective:** plug in a real `LLMProvider` implementation while keeping
every existing safety property.

**Key deliverables:**
- A concrete `LLMProvider` for at least one vendor, isolated behind the
  existing interface (`src/curation/llm_provider.py`).
- The deterministic fallback (`src/curation/fallback.py`) stays the
  default behavior on any provider failure -- not replaced, not bypassed.
- The anti-hallucination guardrail (`src/curation/schema.py`) validated
  against real (not mocked) model output, tightened if real output exposes
  a gap the mocks didn't.
- Basic observability: token/cost tracking per run, and a quality signal
  (e.g. how often the guardrail rejects real output and falls back).

**Done when:** a real LLM call produces a report that passes the guardrail
on real data, and cost/fallback-rate are visible per run.

## 4. Detection Improvements

**Objective:** grow the statistical model beyond the MVP's single-grain,
single-comparison baseline.

**Key deliverables:**
- Peer / hierarchy comparison (`synchronized.py`) to distinguish an
  isolated anomaly from a group-wide move.
- Multi-grain dominance attribution (`attribution.py`) for metrics with a
  real grain hierarchy (e.g. store -> region -> total).
- Cohort/vintage-maturity awareness for metrics where "today" isn't
  directly comparable to a fully-matured historical baseline.
- Richer seasonality handling and baseline methods beyond median+MAD,
  where the data justifies it.
- A `recovered` queue: signals that were flagged before and have returned
  to normal, closing the narrative loop.

**Done when:** at least one metric with a real grain hierarchy and one
cohort-sensitive metric are onboarded and covered by tests exercising these
paths specifically (not just the MVP's two flat metrics).

## 5. Business Context Layer

**Objective:** make the knowledge/priority layer a real, evolvable asset
instead of a TODO-filled skeleton.

**Key deliverables:**
- Versioned business-context content in `knowledge/*.md`, kept in sync with
  the metrics it describes.
- Configurable prioritization rules beyond the current flat weight set
  (e.g. per-stakeholder or per-business-unit sensitivity).
- Explanations that adapt to who's reading, expressed generically in
  configuration/knowledge content -- never a specific company's name or
  facts hardcoded into source code.

**Done when:** two different stakeholder profiles produce visibly different
report framing from the same underlying signals, driven entirely by
config/knowledge content.

## 6. Conversational Layer

**Objective:** let a stakeholder ask questions about already-computed
signals, without turning the LLM into something that computes numbers.

**Key deliverables:**
- A query interface over persisted `SignalContext` / audit-log data --
  answers are grounded in what was actually computed, never freshly
  invented by the model.
- The same anti-hallucination guardrail extended to conversational
  responses, not just the scheduled report.
- Access control and context scoping so a stakeholder only sees signals
  they're entitled to.

**Done when:** a question about a specific past signal gets an answer that
is provably grounded in that signal's stored evidence, with the guardrail
enforced on that path too.

## 7. Production Readiness

**Objective:** make the pipeline safe to run unattended, on a schedule,
against real systems.

**Key deliverables:**
- A scheduler/orchestration layer (e.g. a daily job) replacing manual CLI
  runs.
- Monitoring and failure alerting for the pipeline itself (not just the
  business signals it detects).
- Regression tests against golden datasets, expanded from the MVP's
  hand-built anomaly scenarios toward the fuller golden-day set described
  in `CLEAN_ROOM_SPEC.md`.
- CI/CD (automated tests on every change, automated deploy).
- Cost and performance review once real data volume and a real LLM
  provider are both in the loop.

**Done when:** the pipeline runs on a schedule against real data with no
manual intervention, failures page someone instead of failing silently,
and CI blocks a change that breaks the test suite.
