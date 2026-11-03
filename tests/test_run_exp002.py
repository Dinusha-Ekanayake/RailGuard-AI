"""Tests for ``scripts/run_exp002.py`` on a synthetic CSV (T-002-12)."""

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from railguard.data.metadata import sha256_file
from railguard.evaluation.experiment_config import ExperimentConfig
from scripts.run_exp002 import _event_view, _split_for, main
from tests.synthetic import make_frame

DAY = "2020-03-01"
CONFIG = {
    "features": {
        "window_sizes": ["60s", "5min"],
        "sample_interval": "10s",
        "stride": "60s",
        "min_coverage": 0.8,
        "variants": {"all": [], "no_oil_level": ["Oil_level"]},
    },
    "split": {
        "fit": [f"{DAY} 00:00", f"{DAY} 00:40"],
        "validation": [f"{DAY} 00:40", f"{DAY} 02:00"],
        "test": [f"{DAY} 02:00", f"{DAY} 03:00"],
    },
    "evaluation": {"horizon": "30min", "merge_gap": "10min", "budget_per_24h": 24.0},
    "seed": 7,
    "isolation_forest": {"n_estimators": 20, "max_samples": 32, "contamination": "auto"},
}
WINDOWS = {
    "source": "synthetic",
    "windows": [
        {"id": 1, "start": f"{DAY} 01:40:00", "end": f"{DAY} 01:45:00", "failure": "f",
         "severity": "s", "maintenance": None},
        {"id": 2, "start": f"{DAY} 02:10:00", "end": f"{DAY} 02:20:00", "failure": "f",
         "severity": "s", "maintenance": None},
    ],
}  # fmt: skip


def _inputs(tmp_path: Path) -> list[str]:
    csv = tmp_path / "data.csv"
    make_frame().to_csv(csv)  # the real file has an unnamed index column first
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(CONFIG), encoding="utf-8")
    windows = tmp_path / "windows.yaml"
    windows.write_text(yaml.safe_dump(WINDOWS), encoding="utf-8")
    return [
        "--csv", str(csv), "--config", str(config), "--windows", str(windows),
        "--sha256", sha256_file(csv),
    ]  # fmt: skip


def _run(tmp_path: Path, out: str) -> Path:
    args = [*_inputs(tmp_path), "--out", str(tmp_path / out)]
    main([*args, "--max-gap-s", "60"])
    return tmp_path / out


def test_writes_metrics_run_info_and_results_table(tmp_path: Path) -> None:
    out = _run(tmp_path, "out")

    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert len(metrics["runs"]) == 4
    assert "scores" not in metrics
    info = json.loads((out / "run_info.json").read_text(encoding="utf-8"))
    assert len(info["dataset_sha256"]) == 64
    assert info["seed"] == 7
    assert set(info["features"]) == {"all", "no_oil_level"}
    assert info["config"]["seed"] == 7
    assert "git_commit" in info and "run_seconds" in info
    assert info["git_dirty"] in (True, False, None)
    table = (out / "results.md").read_text(encoding="utf-8")
    assert " of " in table and "%" not in table
    assert "E0" in table and "E1" in table and "no_oil_level" in table
    for banned in ("failure predicted", "defect confirmed", "healthy"):
        assert banned not in table.lower()


def test_metrics_json_is_byte_identical_across_runs(tmp_path: Path) -> None:
    first = (_run(tmp_path, "a") / "metrics.json").read_bytes()
    second = (_run(tmp_path, "b") / "metrics.json").read_bytes()

    assert first == second


def test_plots_are_written_when_matplotlib_is_available(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    out = _run(tmp_path, "out")

    plots = out / "plots"
    assert list(plots.glob("alerts_outside_per_hour.png"))
    for model in ("E0", "E1"):
        for variant in ("all", "no_oil_level"):
            for event_id in (1, 2):
                assert (plots / f"{model}_{variant}_event{event_id}.png").stat().st_size > 0
    assert "event1.png" in (out / "results.md").read_text(encoding="utf-8")


def test_plots_are_skipped_without_matplotlib(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import builtins

    real_import = builtins.__import__

    def fake(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("matplotlib"):
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake)
    out = _run(tmp_path, "out")

    assert (out / "metrics.json").exists()
    assert not (out / "plots").exists()
    assert "matplotlib" in capsys.readouterr().out


def test_missing_checksum_is_refused(tmp_path: Path) -> None:
    args = _inputs(tmp_path)[:-2]  # drop --sha256 and its value

    with pytest.raises(SystemExit) as exc:
        main([*args, "--out", str(tmp_path / "out")])

    assert exc.value.code != 0
    assert not (tmp_path / "out").exists()


def test_checksum_mismatch_exits_before_writing_outputs(tmp_path: Path) -> None:
    args = _inputs(tmp_path)
    args[-1] = "0" * 64

    with pytest.raises(SystemExit) as exc:
        main([*args, "--out", str(tmp_path / "out")])

    assert exc.value.code != 0
    assert not (tmp_path / "out").exists()


def test_event_is_assigned_to_the_split_containing_its_start(tmp_path: Path) -> None:
    from railguard.data.labels import load_failure_windows

    config = ExperimentConfig.from_dict(CONFIG)
    windows_path = tmp_path / "w.yaml"
    windows_path.write_text(yaml.safe_dump(WINDOWS), encoding="utf-8")
    window = load_failure_windows(windows_path)[1]  # starts in test, pre-event range in validation

    assert _split_for(window, config) == "test"


def test_event_view_contains_rows_inside_the_documented_window() -> None:
    import pandas as pd

    index = pd.date_range(f"{DAY} 01:30", f"{DAY} 02:30", freq="1min")
    split = np.where(index < f"{DAY} 02:00", "validation", "test")
    scored = pd.DataFrame({"score": 1.0, "segment_id": 0, "split": split}, index=index)
    from railguard.data.labels import FailureWindow

    window = FailureWindow(
        2, pd.Timestamp(f"{DAY} 02:10"), pd.Timestamp(f"{DAY} 02:20"), "f", "s", None, ""
    )
    view = _event_view(scored, "test", window, pd.Timedelta("30min"))

    assert ((view.index >= window.start) & (view.index <= window.end)).any()
    assert (view["split"] == "test").all()
