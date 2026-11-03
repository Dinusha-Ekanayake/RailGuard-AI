"""Slow end-to-end run of experiment 002 on the real MetroPT-3 CSV (AC-04)."""

import json
import math

import pandas as pd
import pytest

from railguard.data.labels import assign_labels, load_failure_windows
from railguard.data.metropt3 import load_metropt3, validate_metropt3
from railguard.evaluation.experiment import run_experiment
from railguard.evaluation.experiment_config import load_experiment_config
from railguard.preprocessing.segments import assign_segments
from tests.conftest import REAL_CSV, REAL_SHA, ROOT

EVENTS_PER_SPLIT = 2


@pytest.mark.slow
@pytest.mark.skipif(not REAL_CSV.exists(), reason="raw data absent")
def test_exp002_end_to_end_on_real_csv() -> None:
    config = load_experiment_config(ROOT / "configs" / "exp002_metropt_baselines.yaml")
    windows = load_failure_windows(ROOT / "configs" / "metropt3_failure_windows.yaml")
    df, _ = load_metropt3(REAL_CSV, REAL_SHA)
    validate_metropt3(df)
    df["segment_id"] = assign_segments(df["timestamp"])
    labels = assign_labels(df["timestamp"], windows, pd.Timedelta(config.horizon))

    result = run_experiment(df, labels, windows, config)

    assert {(r.model, r.variant) for r in result.runs} == {
        (m, v) for m in ("E0", "E1") for v in ("all", "no_oil_level")
    }
    for run in result.runs:
        assert math.isfinite(run.threshold)
        assert set(run.splits) == {"validation", "test"}
        for evaluation in run.splits.values():
            events = evaluation.metrics.events
            assert len(events) == EVENTS_PER_SPLIT
            assert 0 <= evaluation.metrics.detected <= EVENTS_PER_SPLIT
        ids = {name: [e.event_id for e in run.splits[name].metrics.events] for name in run.splits}
        assert ids == {"validation": [1, 2], "test": [3, 4]}
    assert not any(c.startswith("Oil_level") for c in result.features["no_oil_level"])
    assert any(c.startswith("Oil_level") for c in result.features["all"])
    assert "runs" in json.loads(result.to_json())
