from pathlib import Path

import pandas as pd
import pytest

from railguard.evaluation.experiment_config import ExperimentConfig, load_experiment_config

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "exp002_metropt_baselines.yaml"


def _raw() -> dict:  # type: ignore[type-arg]
    return {
        "features": {
            "window_sizes": ["60s", "5min"],
            "sample_interval": "10s",
            "stride": "60s",
            "min_coverage": 0.8,
            "variants": {"all": [], "no_oil_level": ["Oil_level"]},
        },
        "split": {
            "fit": ["2020-02-01", "2020-04-10"],
            "validation": ["2020-04-10", "2020-06-01"],
            "test": ["2020-06-01", "2020-09-01"],
        },
        "segmentation": {"max_gap_s": 60.0},
        "evaluation": {"horizon": "24h", "merge_gap": "10min", "budget_per_24h": 1.0},
        "seed": 42,
        "isolation_forest": {"n_estimators": 50, "max_samples": 128, "contamination": "auto"},
    }


def test_repo_config_loads() -> None:
    cfg = load_experiment_config(CONFIG_PATH)
    assert isinstance(cfg, ExperimentConfig)
    assert cfg.window_sizes[0] == pd.Timedelta("60s")
    assert cfg.horizon == pd.Timedelta(hours=24)
    assert cfg.merge_gap == pd.Timedelta(minutes=10)
    assert cfg.variants["no_oil_level"] == ("Oil_level",)
    assert cfg.split.test == (pd.Timestamp("2020-06-01"), pd.Timestamp("2020-09-01"))
    assert cfg.budget_per_hour == pytest.approx(1 / 24)
    assert cfg.max_gap_s == 60.0


def test_adjacent_half_open_ranges_are_allowed() -> None:
    ExperimentConfig.from_dict(_raw())


def test_overlapping_splits_rejected() -> None:
    raw = _raw()
    raw["split"]["validation"] = ["2020-04-09", "2020-06-01"]
    with pytest.raises(ValueError, match="overlap"):
        ExperimentConfig.from_dict(raw)


def test_unordered_splits_rejected() -> None:
    raw = _raw()
    raw["split"]["fit"], raw["split"]["test"] = raw["split"]["test"], raw["split"]["fit"]
    with pytest.raises(ValueError, match="order"):
        ExperimentConfig.from_dict(raw)


def test_range_with_start_not_before_end_rejected() -> None:
    raw = _raw()
    raw["split"]["fit"] = ["2020-04-10", "2020-04-10"]
    with pytest.raises(ValueError, match="start"):
        ExperimentConfig.from_dict(raw)


@pytest.mark.parametrize("horizon", ["-1h", "0s"])
def test_non_positive_horizon_rejected(horizon: str) -> None:
    raw = _raw()
    raw["evaluation"]["horizon"] = horizon
    with pytest.raises(ValueError, match="horizon"):
        ExperimentConfig.from_dict(raw)


def test_bad_coverage_rejected() -> None:
    raw = _raw()
    raw["features"]["min_coverage"] = 1.5
    with pytest.raises(ValueError, match="min_coverage"):
        ExperimentConfig.from_dict(raw)


def test_rejects_non_positive_sample_interval() -> None:
    raw = _raw()
    raw["features"]["sample_interval"] = "0s"
    with pytest.raises(ValueError, match="sample_interval"):
        ExperimentConfig.from_dict(raw)


def test_negative_max_gap_rejected() -> None:
    raw = _raw()
    raw["segmentation"]["max_gap_s"] = -1
    with pytest.raises(ValueError, match="max_gap_s"):
        ExperimentConfig.from_dict(raw)
