# EXP-002: MetroPT-3 equipment anomaly baselines (E0, E1)

- **Spec:** `specs/002-metropt-baselines/spec.md` (Approved 2026-11-02)
- **Branch / commit:** `feature/002-metropt-baselines`, run at `a16c5de` with a clean tree (`git_dirty: false`)
- **Status:** Approved by the user (2026-11-03)
- **Raw outputs:** `docs/experiments/exp002/` (`metrics.json`, `run_info.json`, `results.md`, `plots/`)

## Hypothesis

Two simple, unsupervised baselines fitted only on early data assumed to be normal operation can raise an alert (anomaly detected) in or before the documented air-leak windows, at an alert rate outside those windows that stays near the budget of 1 per 24 operating hours (about 0.0417 per hour). These baselines set the reference that any later model (E2, E3, supervised risk) must beat. Nothing here shows a precursor of failure: with 4 events, results are descriptive.

## Dataset

- MetroPT-3 (AirCompressor), SHA-256 `db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24`, as registered in `datasets/metadata/dataset-register.md`.
- 10 s nominal sampling; segments split at gaps, never crossed by a window (ADR-0002).
- 4 documented events, all air leaks on one compressor. Documented windows are approximate. About 96% of rows are unlabelled.

## Split (chronological, half-open, from `configs/exp002_metropt_baselines.yaml`)

| Split | Period | Events | Use |
|---|---|---|---|
| Fit | 2020-02-01 to 2020-04-10 | none | E0 statistics, E1 model. Failure and pre-event rows excluded. |
| Validation | 2020-04-10 to 2020-06-01 | 1, 2 | Threshold choice only. |
| Test | 2020-06-01 to 2020-09-01 | 3, 4 | Reported once, not tuned. |

## Features

Trailing windows only (60 s, 5 min, 15 min, 60 min), scored every 60 s, minimum coverage 0.8, computed inside a segment. Analogue columns: mean, std, min, max. Digital columns: duty cycle and transition count. The segment gap (`segmentation.max_gap_s`, 60 s) is part of the config. Validation and test scoring-row counts are recorded in `run_info.json`. Two variants: `all` and `no_oil_level` (drops `Oil_level`, whose behaviour contradicts its description).

## Baselines

- **E0:** per-feature robust z-score (median, MAD x 1.4826 from the fit period; zero-scale fallback to std; constant features dropped). Score is the maximum absolute z over features.
- **E1:** scikit-learn Isolation Forest, 200 trees, max_samples 256, contamination "auto", seed 42, features standardised on the fit period.
- **Alerting:** score above threshold; exceedances within 10 min merge into one alert episode (never across segments).
- **Threshold:** lowest value on validation whose rate of alerts outside documented windows is at most the budget. The same threshold is applied to test.

## Metrics

An event counts as having an alert when an alert episode overlaps [start - 24 h, end]. Lead time runs from the first alert in that range, clamped to start - 24 h, to the window start (negative means after the window began). Alerts outside documented windows are counted per operating hour (gaps excluded) and are an upper bound on false alerts. Operating hours are summed over the scored rows (after warm-up and coverage filtering), not raw rows, so they are slightly understated and the per-hour rate slightly overstated. When an alert episode began before start - 24 h, the first alert is clamped to start - 24 h, which can overstate lead time by up to the 10 min merge gap.

## Results

| Model | Variant | Split | Events with an alert | Lead time per event (h) | Alerts outside windows per operating hour | Threshold |
|---|---|---|---|---|---|---|
| E0 | all | validation | 1 of 2 | #1: none, #2: 5.12 | 0.0291 | 15191.530442 |
| E0 | all | test | 2 of 2 | #3: 21.53, #4: 15.40 | 0.0743 | 15191.530442 |
| E1 | all | validation | 2 of 2 | #1: -1.20, #2: -0.02 | 0.0118 | 0.665700 |
| E1 | all | test | 2 of 2 | #3: -0.10, #4: 6.00 | 0.0058 | 0.665700 |
| E0 | no_oil_level | validation | 1 of 2 | #1: none, #2: 5.12 | 0.0291 | 15191.530442 |
| E0 | no_oil_level | test | 2 of 2 | #3: 21.53, #4: 15.40 | 0.0743 | 15191.530442 |
| E1 | no_oil_level | validation | 2 of 2 | #1: -1.20, #2: -0.03 | 0.0097 | 0.674443 |
| E1 | no_oil_level | test | 2 of 2 | #3: -0.11, #4: 6.00 | 0.0058 | 0.674443 |

Alert budget: 1 per 24 operating hours = 0.0417 per hour.

### Chance level

An alert in an event's 24 h range does not mean much if alerts that frequent also occur at random times. Using each row's outside-window rate (Poisson approximation, `1 - exp(-rate x 24)`), the chance that at least one alert falls in a given 24 h range anyway is:

| Model | Variant | Split | Expected outside-window alerts per 24 h | Chance of at least one |
|---|---|---|---|---|
| E0 | all, no_oil_level | validation | 0.70 | about 50% |
| E0 | all, no_oil_level | test | 1.78 | about 83% |
| E1 | all | validation | 0.28 | about 25% |
| E1 | all | test | 0.14 | about 13% |
| E1 | no_oil_level | validation | 0.23 | about 21% |
| E1 | no_oil_level | test | 0.14 | about 13% |

Alert clustering would lower these, so they are rough upper figures. They are a reference for reading the event counts, not a statistical test.

## Plots

Per-event score and threshold plots are in `docs/experiments/exp002/plots/` (`<model>_<variant>_event<n>.png`), plus `events_with_alert.png` and `alerts_outside_per_hour.png` for the comparison.

## Reading the results

- E0 has an alert in both test events 21.5 h and 15.4 h ahead, but on test it also alerts about 1.8 times per 24 h outside the windows (about 83% chance of an alert in any 24 h range). Those two early alerts are therefore consistent with chance, and this is not evidence of early warning. E0 missed event 1 on validation, and its outside-window rate on test (0.0743 per hour) is above the 0.0417 budget set on validation, so the threshold did not transfer.
- E1 has an alert in all 4 events and stayed under the budget on both splits. Its lead times are near zero or negative for three events (alerts at or after onset) and 6.00 h for event 4. At its lower alert rate, an alert in the range is less likely by chance (about 13 to 25%), but 4 events cannot separate a signal from luck.
- Every E0 score above its threshold, on validation (28 rows) and test (136 rows), is set by one feature, `TP2__std__60s`, whose fit-period scale is very small (about 0.0004). E0 is therefore effectively a single-feature spike detector on the 60 s variability of the TP2 pressure signal, not a broad multi-signal check.
- Removing `Oil_level` changed nothing for E0 and changed E1 only marginally, so no result depends on that signal.

## Decision

Keep E0 and E1 as the reference baselines for the next experiments. Report event counts and rates as they are; do not describe either model as predicting failures. Use E1 (`all`) as the primary comparator because it stayed within budget on both splits. Keep E0 as a simple reference only: its score is dominated by one near-zero-scale feature, so it is not a broad interpretable baseline. A later experiment could floor the scale or use a quantile score.

## Limitations

- Only 4 events (2 validation, 2 test), all on one compressor and one failure type. Event counts of 1 of 2 or 2 of 2 carry little statistical weight, and no confidence interval is meaningful.
- Documented windows are approximate, and other anomalies may exist outside them, so the outside-window rate is an upper bound on false alerts and says nothing about missed events.
- Lead time depends on the 24 h horizon and on clamping the first alert to start - 24 h; a different horizon changes it.
- The E0 threshold is identical across variants because the same `TP2__std__60s` feature sets it in both, so the variants do not test E0's sensitivity.
- Lead times for E0 are within the range of chance alerts (see Chance level) and should not be read as early warning.
- Lead-time clamping and the operating-hour definition (see Metrics) bias the lead time up and the per-hour rate up slightly.
- `metrics.json` is byte-identical across runs on one platform; the files are written with LF line endings, which should keep it identical across platforms too (not tested on another OS).
- E0 exceeds the budget on test, so the budget is not guaranteed out of sample.
- An event straddling a split boundary would count in both splits. None does with this config.
- Fit rows within the longest window (60 min) after a failure window could include failure rows. No event falls inside the fit period.
- The per-event plot uses the split that contains the window start.
- Unlabelled rows carry no known-normal guarantee; fit statistics assume the fit period is representative normal operation.

## Reproduce

```
.venv\Scripts\python.exe -m scripts.run_exp002 --csv "datasets/raw/metropt+3+dataset/MetroPT3(AirCompressor).csv" --windows configs/metropt3_failure_windows.yaml --config configs/exp002_metropt_baselines.yaml --out docs/experiments/exp002 --sha256 <SHA-256 above>
```

Same code, config and CSV give identical `metrics.json`; `run_info.json` also records run time.
