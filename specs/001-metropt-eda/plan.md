# Plan 001: MetroPT-3 acquisition, validation and EDA

## Approach
Logic lives in small typed modules under `src/railguard/` with no plotting or I/O side effects beyond explicit paths. The notebook only calls these modules. Fast unit tests use tiny synthetic DataFrames. One `slow` test runs against the real CSV.

## Modules / files
| File | Responsibility |
|---|---|
| `src/railguard/data/metadata.py` | `DatasetMetadata` frozen dataclass (name, path, sha256, rows, columns, loaded_at); `sha256_file(path)` streams in chunks |
| `src/railguard/data/errors.py` | `ChecksumMismatchError`, `SchemaValidationError(column, reason)` |
| `src/railguard/data/metropt3.py` | `ANALOG_COLUMNS`, `DIGITAL_COLUMNS`, `SCHEMA`; `load_metropt3(path, expected_sha256: str \| None) -> tuple[DataFrame, DatasetMetadata]` (drops the unnamed index, parses timestamp); `validate_metropt3(df) -> None` |
| `src/railguard/preprocessing/quality.py` | `quality_report(df, timestamp_col) -> QualityReport` (dataclass; `.to_json()`): shape, nulls, duplicates, min/max per column, interval quantiles, gap table, digital cardinality |
| `src/railguard/preprocessing/segments.py` | `assign_segments(ts: Series, max_gap_s: float = 60.0) -> Series[int]` (a new segment when the gap is greater than the threshold) |
| `src/railguard/data/labels.py` | `FailureWindow` dataclass; `load_failure_windows(yaml_path)`; `assign_labels(ts, windows, pre_event_horizon: Timedelta) -> Series[category]`. Precedence: `documented_failure_window` > `pre_event_window` > `unlabelled_or_unknown` |
| `src/railguard/logging_utils.py` | `log_rows(step, before, after)` via the `logging` module |
| `configs/metropt3_failure_windows.yaml` | The 4 events, with source note and maintenance-date caveat |
| `scripts/metropt3_quality_report.py` | CLI: load, validate, report, write `docs/datasets/metropt3_quality.json` and the Parquet file in `datasets/processed/` |
| `notebooks/01_metropt3_eda.ipynb` | Plots: full-period signals, ±24 h around each event, digital-state durations, gap timeline |
| `docs/datasets/metropt3.md` | Dataset card |
| `docs/decisions/ADR-0002-metropt3-windows-and-gaps.md` | Windows of 60 s, 5 min, 15 min and 60 min; 60 s gap threshold; no interpolation |

New dependency: `pyyaml` (core, used to load the config).

## Data flow
raw CSV → checksum → load (drop index, parse ts) → validate → segments → labels → quality report JSON and processed Parquet → notebook.

## Test strategy
- `tests/fixtures/metropt3_small.csv`: about 50 rows of synthetic data with the real schema, including one gap.
- Unit tests for each module. Validation tests are parametrised over each kind of failure (missing column, bad timestamp, unsorted, duplicate, non-binary digital value).
- Boundary tests for labels and segments, per AC-03 and AC-04.
- A `@pytest.mark.slow` integration test on the real file, skipped when the file is absent.

## Risks
- **Memory:** the full CSV is about 1.5 M × 16 columns, roughly 200 MB in pandas. That's acceptable. Use float32 for analogue columns and int8 for digital ones.
- **Timezone:** keep timestamps naive and document this.
- **Notebook drift:** keep logic out of the notebook and run it with `nbconvert --execute` before merging.

## ADRs needed
- ADR-0002 (windows and gap policy).
