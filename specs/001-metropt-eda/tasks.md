# Tasks 001: MetroPT-3 acquisition, validation and EDA

TDD for every task: write the failing test, implement, refactor, then tick the box. Run `pytest -m "not slow"`, `ruff check .` and `mypy` after each task.

| ID | Task | Test | Status |
|---|---|---|---|
| T-001-01 | Add `pyyaml` to core deps; add `tests/fixtures/metropt3_small.csv` (about 50 rows, real schema, one 5-minute gap, unnamed index col) | fixture loads with pandas | [ ] |
| T-001-02 | `data/errors.py`, `data/metadata.py` (`DatasetMetadata`, `sha256_file`) | sha256 of a temp file matches hashlib; dataclass is frozen | [ ] |
| T-001-03 | `logging_utils.log_rows` | caplog captures step, before and after counts | [ ] |
| T-001-04 | `metropt3.load_metropt3`: drop index, parse ts, cast dtypes, checksum check (skipped if `None`) | loads fixture; wrong sha raises `ChecksumMismatchError` | [ ] |
| T-001-05 | `metropt3.validate_metropt3` | parametrised: missing col, unparseable ts, unsorted, duplicate ts, digital value 2 each raise `SchemaValidationError` naming the column; valid fixture passes | [ ] |
| T-001-06 | `preprocessing/segments.assign_segments` | gap == threshold stays in the same segment; threshold + 1 s starts a new one; empty input gives an empty series; fixture gives 2 segments | [ ] |
| T-001-07 | `configs/metropt3_failure_windows.yaml` + `labels.load_failure_windows` | 4 windows load; start < end; event 2 maintenance caveat preserved | [ ] |
| T-001-08 | `labels.assign_labels` | exact start/end inclusive gives failure; horizon boundary gives pre_event; overlap gives failure (precedence); outside gives unlabelled_or_unknown; no row is labelled "healthy" | [ ] |
| T-001-09 | `preprocessing/quality.quality_report` + `.to_json()` | fixture report: correct row count, gap count 1, interval median 10 s, digital cardinality ≤ 2; JSON round-trips | [ ] |
| T-001-10 | `scripts/metropt3_quality_report.py` CLI (paths via args) | runs on fixture into tmp_path; writes JSON and Parquet | [ ] |
| T-001-11 | Slow integration test on the real CSV | 1,516,948 rows, 0 nulls, sha matches the register, 4 windows labelled | [ ] |
| T-001-12 | Run the CLI on the real data; commit `docs/datasets/metropt3_quality.json` | file present; values match the spec findings | [ ] |
| T-001-13 | `notebooks/01_metropt3_eda.ipynb` (calls src only) | `jupyter nbconvert --execute` succeeds | [ ] |
| T-001-14 | ADR-0002; dataset card `docs/datasets/metropt3.md` | review against AC-06 | [ ] |
| T-001-15 | Close out: DEVLOG, CHANGELOG, code-reviewer agent, PR into dev | CI green | [ ] |
