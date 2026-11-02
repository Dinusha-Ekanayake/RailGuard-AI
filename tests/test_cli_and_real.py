import importlib.util
import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from railguard.data.labels import FAILURE, assign_labels, load_failure_windows
from railguard.data.metropt3 import load_metropt3, validate_metropt3
from tests.conftest import REAL_CSV, REAL_SHA, ROOT


def _cli() -> Callable[[list[str]], None]:
    spec = importlib.util.spec_from_file_location(
        "cli", ROOT / "scripts" / "metropt3_quality_report.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    main: Callable[[list[str]], None] = mod.main
    return main


def test_cli_on_fixture(fixture_csv: Path, windows_yaml: Path, tmp_path: Path) -> None:
    rep, pq = tmp_path / "r.json", tmp_path / "p.parquet"
    _cli()(
        [
            "--csv", str(fixture_csv),
            "--windows", str(windows_yaml),
            "--report-out", str(rep),
            "--parquet-out", str(pq),
        ]
    )  # fmt: skip
    assert json.loads(rep.read_text())["rows"] == 50
    assert {"segment_id", "label"} <= set(pd.read_parquet(pq).columns)


@pytest.mark.slow
@pytest.mark.skipif(not REAL_CSV.exists(), reason="raw data absent")
def test_real_csv(windows_yaml: Path) -> None:
    df, _ = load_metropt3(REAL_CSV, REAL_SHA)
    validate_metropt3(df)
    assert len(df) == 1_516_948
    assert int(df.isna().sum().sum()) == 0
    windows = load_failure_windows(windows_yaml)
    labels = assign_labels(df["timestamp"], windows, pd.Timedelta(hours=24))
    for w in windows:
        mask = (df["timestamp"] >= w.start) & (df["timestamp"] <= w.end)
        assert (labels[mask] == FAILURE).all()
        assert mask.sum() > 0, f"window {w.id} has no rows"
