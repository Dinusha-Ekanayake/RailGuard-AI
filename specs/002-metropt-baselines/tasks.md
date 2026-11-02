# Tasks 002: MetroPT-3 equipment anomaly baselines (E0, E1)

TDD for every task: write the failing test, implement, refactor, then tick the box. Run `pytest -m "not slow"`, `ruff check .`, `ruff format --check .` and `mypy` after each task.

| ID | Task | Test | Risk | Status |
|---|---|---|---|---|
| T-002-01 | `configs/exp002_metropt_baselines.yaml` and a typed loader for it (`ExperimentConfig`) | loads; rejects overlapping or unordered split ranges and a negative horizon | low | [x] |
| T-002-02 | Synthetic-frame test helper (2 segments, 10 s, injected step change) in `tests/` | helper returns the expected shape and gap | low | [x] |
| T-002-03 | `features/windows.window_features`: analogue stats, digital duty cycle and transitions, 60 s grid | values match hand-computed ones on a tiny frame; column naming | high | [x] |
| T-002-04 | Leakage and gap guarantees in `window_features` | changing future rows leaves earlier features identical; no window spans a gap; low-coverage rows are dropped and logged | high | [x] |
| T-002-05 | `evaluation/splits`: `assign_split`, `fit_mask` | half-open boundaries; failure and pre-event rows are excluded from fit | high | [ ] |
| T-002-06 | `models/baselines.RobustZScore` | zero-MAD fallback to std; constant feature dropped and logged; outlier scores highest | low | [ ] |
| T-002-07 | `models/baselines.IsolationForestScorer` | same seed gives identical scores; outlier scores higher than normal rows | low | [ ] |
| T-002-08 | `evaluation/alerts.alert_episodes` | merge within the gap; split beyond it; no merge across segments; zero alerts | low | [ ] |
| T-002-09 | `evaluation/event_metrics`: `operating_hours`, `evaluate_events` | episode at exactly `start − horizon` is detected, 1 s earlier is not; episode after `end` is outside windows; lead-time sign; operating hours exclude gaps | high | [ ] |
| T-002-10 | `evaluation/thresholds.select_threshold` | raises on `"test"`; picks the lowest threshold within budget; falls back to the highest candidate (logged) | high | [ ] |
| T-002-11 | `evaluation/experiment.run_experiment` and `ExperimentResult.to_json` | two runs on the synthetic frame give byte-identical JSON; both variants and both models present | high | [ ] |
| T-002-12 | `scripts/run_exp002.py` (metrics JSON, run info, results table, plots) | runs on a synthetic CSV in `tmp_path` (skips without matplotlib); writes all outputs | low | [ ] |
| T-002-13 | Slow end-to-end test on the real CSV | produces validation and test metrics for E0 and E1 in both variants | human | [ ] |
| T-002-14 | Run on the real data; commit `docs/experiments/exp002/` outputs (under 5 MB) | files present; results reported as event counts | human | [ ] |
| T-002-15 | Experiment card `docs/experiments/EXP-002-metropt-baselines.md` | review against AC-05 and REQ-002-07 wording | human | [ ] |
| T-002-16 | Close out: DEVLOG, CHANGELOG, code review, `graphify update .`, PR into dev | CI green | human | [ ] |
