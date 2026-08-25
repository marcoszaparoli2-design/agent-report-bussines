# Next phases

Status snapshot of `CLEAN_ROOM_SPEC.md`'s "Implementation Order" after the
first MVP. Steps 1-7 (roughly) are done; everything below is deliberately
deferred, not forgotten.

## Deferred from this MVP

- **Peer check / hierarchy check** (`anomaly_detection/synchronized.py`) --
  distinguishing "this entity moved alone" from "the whole group moved
  together". Needs a second, structurally-related grain in the fixtures
  before it's testable.
- **Multi-grain dominance attribution** (`anomaly_detection/attribution.py`)
  -- only relevant once a real grain hierarchy exists (e.g. store -> region
  -> total); the MVP's two example metrics are single-grain.
- **`immature_vintage` gate** -- for cohort/maturity-sensitive rate metrics.
  Not needed until a metric with that shape is added.
- **Elaborate golden-day scenario set** (`tests/golden/`) -- the MVP proves
  the pipeline against two hand-designed anomalies; a full golden day
  (cold start, recovered, systemic move + cascade, etc., per the spec) is a
  bigger investment worth doing once more metrics exist.
- **Real warehouse adapter** (BigQuery/Postgres/etc. implementing
  `DataSource`) -- the MVP only ships `FixtureDataSource`.
- **Delivery channel adapter** (Slack/Teams/webhook implementing actual
  HTTP delivery + idempotency history) -- `config/delivery_channels.yaml`
  and `.env.example` are ready for one, but no adapter is implemented yet.
- **Real `LLMProvider` implementation** -- the interface and guardrail exist
  and are tested against mock providers; no vendor SDK is wired in.
- **`recovered` queue** -- needs a persisted "what did we say yesterday"
  history, which needs a real delivery run to exist first.
- **Skills / scaffolding tooling** (`/add-metric`, `/replay-day`-equivalent
  commands) -- convenience automation, worth building once the manual
  process (hand-writing a `metrics/<name>/contract.yaml`) is well understood.
- **Conversational/Q&A experience** -- the modular boundary between
  deterministic scoring (`anomaly_detection/`, `prioritization/`) and
  narrative generation (`curation/`) is deliberate so a future
  conversational layer can query the same `SignalContext` objects instead
  of the rendered report.

## Explicitly out of scope for now

- Anything tied to a specific company's real metrics, thresholds, or
  taxonomy -- `metrics/conversion_rate` and `metrics/revenue` are generic
  placeholders; replace them (or add more) via the same contract pattern.
