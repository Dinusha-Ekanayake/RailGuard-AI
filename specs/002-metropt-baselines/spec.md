# Spec 002: MetroPT-3 equipment anomaly baselines (E0, E1)

- **Status:** Approved (2026-11-02)
- **Master doc refs:** §6.2, §7.1 (E0, E1), §7.6, §11.1, §14 (Phase 2), §16.1
- **Branch:** `feature/002-metropt-baselines`
- **Depends on:** spec 001 (loader, segments, labels), ADR-0002 (windows and gap policy)

## Problem / why
Phase 2's exit criterion is "a reproducible experiment with false-alert and event-level metrics". Spec 001 gives a validated, segmented and labelled MetroPT-3 frame, but nothing yet scores it. Two simple baselines are needed before anything more advanced (E2, E3 or a supervised failure-risk model) can be judged: an interpretable statistical threshold (E0) and an Isolation Forest (E1). Both are evaluated the same way, at event level, without tuning and testing on the same events.

## What the EDA tells us (spec 001)
- 10 s sampling; 332 contiguous segments; windows are 60 s, 5 min, 15 min and 60 min (ADR-0002).
- Only 4 documented events, all air leaks on one compressor; 96% of rows are unknown, not healthy.
- In the failure windows the compressor is under load almost all the time (DV_eletric active 99.5% vs 16.1% overall; COMP active 0.4% vs 83.7%). Duty-cycle features over a window are therefore the obvious first features. This is an association over 4 events, not a validated precursor.
- `Oil_level` is active 90% of the time, which contradicts its description. It is kept as a feature but flagged; no conclusion rests on it alone.

## Scope
### In scope
- **Window features** (`src/railguard/features/`): trailing windows only (no centred windows, no future rows), computed within a segment and never across a gap. Scored on a 60 s grid to keep memory bounded (about 250 k scoring points instead of 1.5 M rows).
  - Analogue columns: mean, std, min, max per window.
  - Digital columns: duty cycle (share of time active) and transition count per window.
  - Warm-up: a window with less than 80% of its expected samples gives no feature row.
- **Chronological, event-aware split** (fixed, recorded in config):
  | Split | Period | Events | Use |
  |---|---|---|---|
  | Fit | 2020-02-01 → 2020-04-10 | none | Fit E0 statistics and E1 model. Failure and pre-event rows are excluded. |
  | Validation | 2020-04-10 → 2020-06-01 | 1, 2 | Choose the alert threshold. |
  | Test | 2020-06-01 → 2020-09-01 | 3, 4 | Report once, never tune. |
- **E0, statistical baseline:** per-feature robust z-score (median and MAD from the fit period); the window score is the maximum absolute z over features. No hand-set physical limits.
- **E1, Isolation Forest:** scikit-learn, fixed seed, features standardised on the fit period.
- **Alerting:** a score above the threshold starts an alert; consecutive exceedances within 10 min merge into one alert episode.
- **Threshold selection** (validation only): pick the lowest threshold whose rate of alerts outside documented windows is at most the alert budget (default 1 per 24 operating hours), then report event recall on validation at that threshold.
- **Event-level metrics** (`src/railguard/evaluation/`):
  - Event detected: at least one alert in `[start − horizon, end]`; horizon default 24 h (configurable, an assumption).
  - Detection lead time: `start − first alert time` (negative means the alert came after the window began).
  - Alerts outside documented windows per operating hour. Operating hours exclude gaps. This is an **upper bound** on false alerts, because unknown rows are not known to be healthy.
  - Qualitative plots of score and threshold around each event.
- **`Oil_level` check (risk R11):** run E0 and E1 with and without `Oil_level` features and report both, so no result depends on a signal that contradicts its description.
- **Experiment runner:** one CLI that runs E0 and E1 from a YAML config and writes metrics JSON, plots and an experiment card (`docs/experiments/EXP-002-metropt-baselines.md`) recording dataset checksum, time ranges, feature set, split, parameters, seed and git commit.

### Non-goals
- E2 (robust covariance / One-Class SVM), E3 (autoencoder) and the supervised failure-risk model (§7.2). Each gets its own spec.
- MLflow (see open question 1).
- Any API, database or UI integration.
- Claims about other failure modes, other compressors or other fleets.

## Requirements
- REQ-002-01: Features at time *t* use only rows with timestamp ≤ *t* from the same segment. A test proves that changing any future row leaves earlier features unchanged.
- REQ-002-02: No feature window spans a segment boundary; warm-up windows below 80% coverage are dropped and the count is logged.
- REQ-002-03: Rows labelled `documented_failure_window` or `pre_event_window` are excluded from fitting. The split boundaries come from config and are logged.
- REQ-002-04: The threshold is chosen on validation only. Test metrics are computed once with that frozen threshold, and the runner refuses to tune on the test split.
- REQ-002-05: Runs are deterministic: the same config and data give byte-identical metrics JSON.
- REQ-002-06: Every run records dataset SHA-256, config, seed, feature list and git commit in its outputs.
- REQ-002-07: All user-facing text uses "anomaly detected" / "alert". Nothing says "failure predicted", "defect confirmed" or "healthy".

## Acceptance criteria
- [ ] AC-01: `pytest -m "not slow"` passes with ≥ 80% coverage on new modules, using synthetic fixtures.
- [ ] AC-02: A future-leakage test (REQ-002-01) and a gap-boundary test (REQ-002-02) pass.
- [ ] AC-03: Metric tests cover an alert exactly at `start − horizon`, an alert just before it, an alert after `end`, merged episodes, and zero alerts.
- [ ] AC-04: A `slow` test runs E0 and E1 end to end on the real CSV and produces metrics JSON for validation and test.
- [ ] AC-05: The experiment card reports, for E0 and E1 on validation and test: events detected (of 2), lead time per event, alerts outside windows per operating hour, and the chosen threshold, with limitations stated (4 events, approximate windows, upper-bound false-alert rate).
- [ ] AC-06: Ruff, mypy (strict) and CI are green.

## Data caveats & safety boundary
- With 2 validation and 2 test events, every recall figure is one of 0%, 50% or 100%. Results are reported as counts ("1 of 2"), never as a percentage alone, and are not evidence of a working detector.
- The fit period (Feb to early Apr) is assumed to be mostly normal operation. That is an assumption; it is unlabelled.
- Window timestamps are approximate and naive local time.
- The baselines are analytical experiments. Their output never overrides the deterministic rule engine and is never presented as a safety decision.

## Resolved questions (2026-11-02)
1. **MLflow:** deferred to the phase that adds Docker Compose. Runs are recorded as metrics JSON plus an experiment card.
2. **Split:** the fixed chronological 2 + 2 split above. Leave-one-event-out may follow later as a sensitivity check.
3. **Alert budget:** at most 1 alert outside documented windows per 24 operating hours.
