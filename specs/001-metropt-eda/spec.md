# Spec 001: MetroPT-3 acquisition, validation and EDA

- **Status:** Approved (2026-11-02)
- **Master doc refs:** §5.1, §6.1, §6.2, §14 (Phase 1), §15
- **Branch:** `feature/001-metropt-eda`

## Problem / why
Every later equipment experiment (Phase 2 baselines, failure-risk work, a possible evaluation paper) depends on a trustworthy, documented view of MetroPT-3. That covers its real schema, sampling behaviour, gaps and the documented failure windows. Today all of that exists only as assumptions in the master doc, and some of those assumptions are wrong (see Findings).

## Findings from the initial profile (2026-11-02, local CSV)
| Item | Source claim | Observed |
|---|---|---|
| Rows | 15,169,480 (description PDF); ~1.52 M (master doc) | **1,516,948** rows plus an unnamed index column |
| Sampling | 1 Hz (PDF) | **Median 10 s** (p1 9 s, p99 12 s). **Confirmed online:** the UCI page says "1516948 data points collected at 0.1Hz". The PDF's 1 Hz and 15.2 M figures describe the original logging, not this file. |
| Time span | Feb–Aug 2020 | 2020-02-01 00:00:00 → **2020-09-01 03:59:50** |
| Gaps | not stated | 331 gaps > 60 s, 160 > 1 h, longest ≈ 48 h |
| Quality | — | 0 nulls, 0 duplicate timestamps, sorted, 100% timestamp parse rate |
| Digital signals | binary | All 8 are in {0, 1} (to be confirmed). `DV_eletric` is misspelt in the source and the name is kept. |
| Failure table | 4 air-leak events | The table numbers two events "#1". Event 2 lists "Maintenance on 30Apr" but the failure is 29–30 May, probably a typo. The timezone is not stated. |
| Paper DOI | master doc: …9564201 | **Verified:** `10.1109/DSAA53316.2021.9564181` resolves to the paper; …9564201 returns 404. The master doc has a typo. Dataset DOI: `10.24432/C5VW3R`. Licence: CC BY 4.0. |

**Consequence:** the master doc's 10 s and 30 s rolling windows (§5.1) would hold only 1–3 samples. Window candidates move to **60 s, 5 min, 15 min and 60 min**. This needs an ADR.

## Scope
### In scope
- A loader that reads the raw CSV unchanged, enforces a documented schema and returns `(DataFrame, DatasetMetadata)`.
- Data-quality report: shape, dtypes, parse rate, duplicates, nulls, value ranges, interval distribution, gap table, digital-signal cardinality.
- A failure-window label table (`configs/metropt3_failure_windows.yaml`) holding the 4 reported events, with corrections noted next to each entry and the labels `documented_failure_window`, `pre_event_window` and `unlabelled_or_unknown`.
- A gap-segmentation policy: contiguous operating segments split at gaps greater than a configurable threshold, with no interpolation across gaps.
- A processed Parquet output in `datasets/processed/` (gitignored).
- EDA notebook `notebooks/01_metropt3_eda.ipynb`: per-signal plots over the full period and around each event window, plus digital-signal state analysis. Its logic lives in `src/`, and the notebook only calls it.
- Dataset card `docs/datasets/metropt3.md` and an update to the dataset register.
- ADR-0002: window sizes and gap policy, given 10 s sampling.

### Non-goals
- Feature engineering beyond what EDA needs (Phase 2).
- Any anomaly model or threshold tuning (Phase 2).
- Fetching through `ucimlrepo`. The local, checksummed CSV is canonical; a download script is optional.

## Requirements
- REQ-001-01: The loader verifies the file's SHA-256 against the register and fails clearly on a mismatch.
- REQ-001-02: The loader validates 15 named signal columns plus `timestamp`, numeric dtypes, a timestamp parse rate of 1.0, monotonic order, no duplicates, and digital columns in {0, 1}. Each violation raises a typed error that names the column.
- REQ-001-03: Every transformation logs its row counts before and after.
- REQ-001-04: The quality report is deterministic and serialisable to JSON in `docs/datasets/`.
- REQ-001-05: Failure windows load from YAML into a label table. A function assigns each timestamp exactly one label. The pre-event horizon is configurable and is not a fact.
- REQ-001-06: Gap segmentation returns segment IDs. Gaps greater than the threshold (default 60 s, configurable) are never bridged.
- REQ-001-07: Nothing in `datasets/raw/` is modified.

## Acceptance criteria
- [ ] AC-01: `pytest -m "not slow"` passes with ≥ 80% coverage on new modules, using small synthetic fixtures (CI has no raw data).
- [ ] AC-02: A `slow` test runs the loader and validation on the real CSV and matches the profile above (1,516,948 rows, 0 nulls).
- [ ] AC-03: Tests cover label assignment at the boundaries: exact window start and end, overlapping horizons, and timestamps outside every window.
- [ ] AC-04: Tests cover gap segmentation for a gap exactly at the threshold, one just above it, and an empty input.
- [ ] AC-05: The notebook runs top to bottom from a clean kernel and shows all 4 event windows.
- [ ] AC-06: The dataset card states the 10 s sampling finding, the PDF inconsistencies, the label semantics and the prohibited claims.
- [ ] AC-07: ADR-0002 is accepted. Ruff, mypy (strict) and CI are green.

## Data caveats & safety boundary
- Rows outside the reported windows are **unlabelled**, not healthy.
- The four events are all air leaks on one compressor. Nothing here generalises to other failure modes or other units.
- Event-window timestamps are approximate and their timezone is unknown. They are treated as local naive time, the same as the CSV.

## Resolved questions
1. **Event 2 maintenance date:** the UCI page, the description PDF and mirrors all say "30Apr", which comes before the failure. No source corrects it. **Decision:** the window timestamps (2020-05-29 23:30 → 2020-05-30 06:00) are consistent everywhere and are what labelling uses. The maintenance date is stored as `"2020-04-30 (as published; likely 2020-05-30, unverified)"` and is not used for labels.
2. **Notebook dependencies:** the `analysis` extra is installed (approved).
