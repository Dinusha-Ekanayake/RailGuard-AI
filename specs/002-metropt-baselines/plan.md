# Plan 002: MetroPT-3 equipment anomaly baselines (E0, E1)

## Approach
Reuse spec 001 for loading, validation, segments and labels. Add four small typed modules: features, splits, models and event evaluation. They have no plotting and no I/O beyond explicit paths. One CLI runs the whole experiment from a YAML config. Plotting lives in the CLI script, not in `src/railguard`, because CI installs only the `dev` extra and mypy checks the package without matplotlib.

Every function that takes timestamps assumes they are sorted, unique and segmented. They check this and raise `ValueError` otherwise.

## Modules / files
| File | Responsibility |
|---|---|
| `configs/exp002_metropt_baselines.yaml` | Windows (60 s, 5 min, 15 min, 60 min), 60 s scoring stride, 0.8 minimum coverage, split boundaries, 24 h horizon, 10 min alert-merge gap, budget of 1 alert per 24 h, seed, Isolation Forest parameters, feature variants (`all`, `no_oil_level`) |
| `src/railguard/features/windows.py` | `FeatureConfig` dataclass. `window_features(df, config) -> DataFrame` indexed by scoring timestamp, with a `segment_id` column. Trailing time-based rolling per segment (`closed="right"`, so rows ≤ t only). Analogue: mean, std, min, max. Digital: duty cycle and transition count. Coverage is the row count divided by the expected count, and rows below `min_coverage` are dropped (count logged). Scoring rows are the last row in each 60 s bucket per segment. Columns are named `<signal>__<stat>__<window>`. Computed one window size at a time to cap memory (about 270 MB peak). |
| `src/railguard/evaluation/splits.py` | `SplitConfig` (fit, validation, test as half-open `[start, end)` ranges). `assign_split(ts) -> Series[category]`. `fit_mask(split, labels)` excludes failure and pre-event rows. |
| `src/railguard/models/baselines.py` | `Scorer` protocol (`fit(X)`, `score(X) -> ndarray`, higher means more anomalous). `RobustZScore`: median and MAD × 1.4826 from fit data. A feature with zero scale falls back to std; if that is also zero it is dropped and logged. The score is the max absolute z. `IsolationForestScorer`: `StandardScaler` plus `IsolationForest(random_state=seed)`, score = `-score_samples`. |
| `src/railguard/evaluation/alerts.py` | `AlertEpisode(start, end, peak_score)` frozen dataclass. `alert_episodes(scores: Series, threshold, merge_gap) -> list[AlertEpisode]`. An episode never spans a segment boundary. |
| `src/railguard/evaluation/event_metrics.py` | `operating_hours(ts, segment_ids)` sums segment durations, so gaps are excluded. `EventResult(event_id, detected, lead_time_s, first_alert)`. `evaluate_events(episodes, windows, horizon, op_hours) -> EventMetrics`. An event is detected when an episode overlaps `[start − horizon, end]`. Episodes that overlap no such range count as alerts outside documented windows, reported per operating hour. |
| `src/railguard/evaluation/thresholds.py` | `select_threshold(scores, split_name, windows, horizon, op_hours, budget_per_hour, merge_gap) -> float`. Raises `ValueError` if `split_name == "test"` (REQ-002-04). Candidates are validation-score quantiles from 0.90 to 0.99999 (fixed grid). It returns the lowest candidate within the budget, or the highest candidate (logged) if none is. |
| `src/railguard/evaluation/experiment.py` | `run_experiment(df, labels, windows, config) -> ExperimentResult`, pure and with no files written. For each model and feature variant: fit on the fit mask, score all splits, select the threshold on validation, evaluate validation and test. `ExperimentResult.to_json()` uses sorted keys, floats rounded to 6 dp and no run time, so output is deterministic. |
| `scripts/run_exp002.py` | CLI. Loads with the checksum, validates, segments, labels, runs the experiment, then writes `docs/experiments/exp002/metrics.json`, `run_info.json` (dataset SHA, config, seed, feature list, git commit, run time) and `results.md` (table). Event plots go to `plots/`, created with matplotlib Agg inside the script. |
| `docs/experiments/EXP-002-metropt-baselines.md` | Experiment card: hypothesis, dataset version, split, baselines, metrics, plots, result, decision and limitations. |

No new runtime dependency: scikit-learn is already core. matplotlib comes from the `analysis` extra and is used only by the script.

## Data flow
raw CSV → `load_metropt3` (checksum) → `validate_metropt3` → `assign_segments` → `assign_labels` → `window_features` (60 s grid) → `assign_split` → per model and variant: `fit` (fit split, no failure or pre-event rows) → `score` (all splits) → `select_threshold` (validation only) → `alert_episodes` → `evaluate_events` (validation, test) → metrics JSON, results table, plots, then the experiment card (written by hand from `results.md`).

## Test strategy
- **Synthetic fixtures built in code** (no new CSV): a 2-segment frame at 10 s with an injected step change. Small enough for fast tests.
- **Leakage (REQ-002-01):** compute features, change every row after time t, recompute, and assert that features at or before t are identical.
- **Gap boundary (REQ-002-02):** the first scoring rows after a gap have no window that reaches back across it, and warm-up rows below coverage are dropped.
- **Splits:** boundaries are half-open, and the fit mask excludes failure and pre-event rows.
- **Models:** the zero-MAD fallback and the dropped feature; IF scores are deterministic with a fixed seed; an injected outlier scores higher than normal rows.
- **Alerts:** merging within the gap, no merge across segments, zero alerts.
- **Event metrics (AC-03):** an episode exactly at `start − horizon` counts, one 1 s earlier does not, one after `end` is counted as outside windows, plus lead-time sign and operating hours with gaps.
- **Threshold:** raises on `"test"`; picks the lowest threshold within budget on a crafted score series.
- **Experiment:** two runs give byte-identical JSON (REQ-002-05).
- **CLI:** `pytest.importorskip("matplotlib")`, then run on a synthetic CSV in `tmp_path`.
- **Slow:** end to end on the real CSV (AC-04).

## Risks
- **Memory or time on the full data:** compute one window size at a time and downsample to the 60 s grid immediately. Expected runtime is minutes. If the 60 min rolling `std` is slow, switch to cumulative-sum formulas.
- **No threshold meets the budget:** fall back to the highest candidate, log it and report it in the card. Do not widen the grid silently.
- **A degenerate fit period** (for example a digital signal constant in Feb to Apr): handled by the zero-scale fallback and the dropped-feature log.
- **Over-reading results:** with 2 + 2 events, report counts ("1 of 2") and list the limitations in the card.

## ADRs needed
None. The window and gap policy is ADR-0002, and the evaluation protocol is fixed by this spec. If the threshold-selection rule changes after the first run, that change needs an ADR.
