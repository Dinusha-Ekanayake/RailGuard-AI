# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: SemVer, with milestone tags on `main`.

## [Unreleased]
### Added
- Phase 0 scaffold: package skeleton, venv config, SDD templates, governance docs, CI.
- MetroPT-3 loader, schema validation, gap segmentation, failure-window labels, quality report, EDA notebook, dataset card and ADR-0002.
- MetroPT-3 baselines (spec 002): trailing window features, chronological fit, validation and test split, E0 robust z-score and E1 Isolation Forest baselines, alert episodes and event-level metrics (events with an alert, lead time, alerts outside documented windows per operating hour).
- EXP-002 experiment runner (`scripts/run_exp002.py`) and experiment card `docs/experiments/EXP-002-metropt-baselines.md`, reporting E0 and E1 results as event counts.
