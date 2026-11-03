"""Tests for ``evaluation.experiment.run_experiment`` (T-002-11)."""

import json

import pandas as pd
import pytest

from railguard.data.labels import FailureWindow, assign_labels
from railguard.evaluation.experiment import ExperimentResult, run_experiment
from railguard.evaluation.experiment_config import ExperimentConfig
from tests.synthetic import make_frame

DAY = "2020-03-01"


def _config() -> ExperimentConfig:
    return ExperimentConfig.from_dict(
        {
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
            "segmentation": {"max_gap_s": 60.0},
            "evaluation": {"horizon": "30min", "merge_gap": "10min", "budget_per_24h": 24.0},
            "seed": 7,
            "isolation_forest": {"n_estimators": 20, "max_samples": 32, "contamination": "auto"},
        }
    )


def _windows() -> list[FailureWindow]:
    def win(i: int, start: str, end: str) -> FailureWindow:
        return FailureWindow(i, pd.Timestamp(start), pd.Timestamp(end), "f", "s", None, "")

    return [win(1, f"{DAY} 01:40", f"{DAY} 01:45"), win(2, f"{DAY} 02:10", f"{DAY} 02:20")]


def _run(config: ExperimentConfig | None = None) -> ExperimentResult:
    config = config or _config()
    df = make_frame()
    windows = _windows()
    labels = assign_labels(df["timestamp"], windows, config.horizon)
    return run_experiment(df, labels, windows, config)


def test_both_models_and_variants_are_present() -> None:
    result = _run()

    assert {(r.model, r.variant) for r in result.runs} == {
        (m, v) for m in ("E0", "E1") for v in ("all", "no_oil_level")
    }
    for run in result.runs:
        assert set(run.splits) == {"validation", "test"}


def test_variant_removes_oil_level_features() -> None:
    result = _run()

    removed = set(result.features["all"]) - set(result.features["no_oil_level"])
    assert removed
    assert all(f.startswith("Oil_level__") for f in removed)
    assert set(result.features["no_oil_level"]) <= set(result.features["all"])


def test_unknown_removed_signal_raises() -> None:
    raw = _raw(_config())
    raw["features"]["variants"] = {"typo": ["Oil_Level"]}
    config = ExperimentConfig.from_dict(raw)
    df = make_frame()
    windows = _windows()
    labels = assign_labels(df["timestamp"], windows, config.horizon)

    with pytest.raises(ValueError, match="Oil_Level"):
        run_experiment(df, labels, windows, config)


def test_two_runs_give_byte_identical_json() -> None:
    assert _run().to_json() == _run().to_json()


def test_json_is_sorted_rounded_and_parseable() -> None:
    text = _run().to_json()
    data = json.loads(text)

    assert data["seed"] == 7
    assert list(data) == sorted(data)
    run = data["runs"][0]
    assert isinstance(run["threshold"], float)
    assert run["threshold"] == round(run["threshold"], 6)
    assert "failure predicted" not in text


def test_fit_rows_exclude_pre_event_rows() -> None:
    # A pre-event window covering the whole fit split leaves nothing to fit on.
    config = _config()
    df = make_frame()
    windows = [
        FailureWindow(
            1, pd.Timestamp(f"{DAY} 00:41"), pd.Timestamp(f"{DAY} 00:45"), "f", "s", None, ""
        )
    ]
    big = ExperimentConfig.from_dict(
        {
            **_raw(config),
            "segmentation": {"max_gap_s": 60.0},
            "evaluation": {"horizon": "2h", "merge_gap": "10min", "budget_per_24h": 24.0},
        }
    )
    labels = assign_labels(df["timestamp"], windows, big.horizon)

    with pytest.raises(ValueError, match="fit"):
        run_experiment(df, labels, windows, big)


def test_empty_test_split_raises() -> None:
    raw = _raw(_config())
    raw["split"]["test"] = ["2021-01-01", "2021-01-02"]
    config = ExperimentConfig.from_dict(raw)
    df = make_frame()
    windows = _windows()
    labels = assign_labels(df["timestamp"], windows, config.horizon)

    with pytest.raises(ValueError, match="test"):
        run_experiment(df, labels, windows, config)


def _raw(config: ExperimentConfig) -> dict:  # type: ignore[type-arg]
    ranges = {
        n: [str(getattr(config.split, n)[0]), str(getattr(config.split, n)[1])]
        for n in ("fit", "validation", "test")
    }
    return {
        "features": {
            "window_sizes": ["60s", "5min"],
            "sample_interval": "10s",
            "stride": "60s",
            "min_coverage": 0.8,
            "variants": {"all": [], "no_oil_level": ["Oil_level"]},
        },
        "split": ranges,
        "segmentation": {"max_gap_s": 60.0},
        "evaluation": {"horizon": "30min", "merge_gap": "10min", "budget_per_24h": 24.0},
        "seed": 7,
        "isolation_forest": {"n_estimators": 20, "max_samples": 32, "contamination": "auto"},
    }


def test_test_split_rows_never_change_threshold_or_validation() -> None:
    # Adversarial (reviewer, REQ-002-04): wildly perturbing every test-split row must leave
    # each frozen threshold and every validation result unchanged.
    config = _config()
    windows = _windows()
    df = make_frame()
    labels = assign_labels(df["timestamp"], windows, config.horizon)
    base = run_experiment(df, labels, windows, config)

    poisoned = df.copy()
    in_test = poisoned["timestamp"] >= pd.Timestamp(f"{DAY} 02:00")
    for col in ("TP2", "TP3", "H1", "Oil_temperature", "Motor_current", "Oil_level"):
        poisoned.loc[in_test, col] = poisoned.loc[in_test, col] * 50.0 + 1e4
    other = run_experiment(poisoned, labels, windows, config)

    assert in_test.sum() > 0
    for a, b in zip(base.runs, other.runs, strict=True):
        assert (a.model, a.variant) == (b.model, b.variant)
        assert a.threshold == b.threshold
        assert a.splits["validation"] == b.splits["validation"]
    assert any(
        a.splits["test"] != b.splits["test"] for a, b in zip(base.runs, other.runs, strict=True)
    )


def test_scores_are_kept_in_memory_but_not_in_json() -> None:
    result = _run()

    assert set(result.scores) == {(r.model, r.variant) for r in result.runs}
    frame = result.scores[("E0", "all")]
    assert {"score", "segment_id", "split"} <= set(frame.columns)
    assert set(frame["split"]) == {"validation", "test"}
    assert "score" not in result.to_json()
