"""Tests for ``features.windows.window_features`` (T-002-03, T-002-04; REQ-002-01, REQ-002-02)."""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from railguard.data.metropt3 import ANALOG_COLUMNS, DIGITAL_COLUMNS, TIMESTAMP_COL
from railguard.evaluation.experiment_config import load_experiment_config
from railguard.features.windows import FeatureConfig, window_features

from .synthetic import START, STEP_COLUMN, make_frame

SEC = pd.Timedelta(seconds=1)
CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "exp002_metropt_baselines.yaml"


def _config(windows: tuple[str, ...] = ("60s", "300s"), min_coverage: float = 0.8) -> FeatureConfig:
    return FeatureConfig(
        window_sizes=tuple(pd.Timedelta(w) for w in windows),
        sample_interval=pd.Timedelta("10s"),
        stride=pd.Timedelta("60s"),
        min_coverage=min_coverage,
    )


def _tiny_frame() -> pd.DataFrame:
    """One segment, 12 rows at 10 s. TP2 = 0..11, COMP follows a fixed pattern."""
    ts = pd.date_range(START, periods=12, freq="10s")
    data: dict[str, object] = {TIMESTAMP_COL: ts}
    for col in ANALOG_COLUMNS:
        data[col] = np.arange(12, dtype="float64") if col == "TP2" else 1.0
    for col in DIGITAL_COLUMNS:
        data[col] = 0
    data["COMP"] = [0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0]
    return pd.DataFrame(data).assign(segment_id=0)


# --- T-002-03: values, naming, grid -------------------------------------------------


def test_values_match_hand_computed_ones() -> None:
    out = window_features(_tiny_frame(), _config(windows=("60s",)))

    first, second = out.iloc[0], out.iloc[1]  # rows at 50 s and 110 s
    assert out.index[0] == START + 50 * SEC
    assert first["TP2__mean__60s"] == pytest.approx(2.5)
    assert first["TP2__min__60s"] == 0.0
    assert first["TP2__max__60s"] == 5.0
    assert first["TP2__std__60s"] == pytest.approx(np.std(np.arange(6), ddof=1))
    assert second["TP2__mean__60s"] == pytest.approx(8.5)
    assert first["COMP__duty__60s"] == pytest.approx(3 / 6)
    assert first["COMP__transitions__60s"] == 2
    assert second["COMP__duty__60s"] == pytest.approx(4 / 6)
    assert second["COMP__transitions__60s"] == 2


def test_column_names_follow_signal_stat_window_pattern() -> None:
    out = window_features(make_frame(), _config())

    expected = {
        f"{c}__{s}__{w}"
        for c in ANALOG_COLUMNS
        for s in ("mean", "std", "min", "max")
        for w in ("60s", "300s")
    }
    expected |= {
        f"{c}__{s}__{w}"
        for c in DIGITAL_COLUMNS
        for s in ("duty", "transitions")
        for w in ("60s", "300s")
    }
    assert set(out.columns) == expected | {"segment_id"}


def test_scoring_rows_sit_on_the_stride_grid_one_per_bucket_per_segment() -> None:
    out = window_features(make_frame(), _config())

    assert out.index.name == TIMESTAMP_COL
    assert out.index.is_monotonic_increasing
    buckets = list(zip(out["segment_id"], out.index.floor("60s"), strict=True))
    assert len(buckets) == len(set(buckets))
    # every scoring row is the last source row of its bucket within its segment
    df = make_frame()
    df["bucket"] = df[TIMESTAMP_COL].dt.floor("60s")
    last_rows = df.groupby(["segment_id", "bucket"])[TIMESTAMP_COL].max()
    assert set(out.index) <= set(last_rows)
    assert set(out["segment_id"].unique()) == {0, 1}


def test_analogue_step_shows_in_rolling_mean() -> None:
    df = make_frame(step_at=180)
    out = window_features(df, _config(windows=("60s",)))
    seg1 = out[out["segment_id"] == 1][f"{STEP_COLUMN}__mean__60s"]

    assert seg1.iloc[-1] - seg1.iloc[0] == pytest.approx(5.0, abs=0.5)


def test_from_experiment_config_copies_window_settings() -> None:
    cfg = load_experiment_config(CONFIG_PATH)
    features = FeatureConfig.from_experiment(cfg)

    assert features.window_sizes == cfg.window_sizes
    assert features.sample_interval == cfg.sample_interval
    assert features.stride == cfg.stride
    assert features.min_coverage == cfg.min_coverage


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: d.drop(columns=["TP2"]), "missing"),
        (lambda d: d.drop(columns=["segment_id"]), "missing"),
        (lambda d: d.iloc[::-1].reset_index(drop=True), "sorted"),
        (
            lambda d: pd.concat([d, d.iloc[[3]]], ignore_index=True).sort_values(TIMESTAMP_COL),
            "unique",
        ),
    ],
)
def test_rejects_malformed_input(mutate, message: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match=message):
        window_features(mutate(_tiny_frame()), _config())


def test_empty_frame_gives_empty_features() -> None:
    out = window_features(_tiny_frame().iloc[0:0], _config())

    assert out.empty
    assert "segment_id" in out.columns


# --- T-002-04: leakage and gap guarantees -------------------------------------------


def test_changing_future_rows_leaves_earlier_features_identical() -> None:
    df = make_frame()
    baseline = window_features(df, _config())
    cut = baseline.index[len(baseline) // 2 + 10]

    changed = df.copy()
    future = changed[TIMESTAMP_COL] > cut
    changed.loc[future, list(ANALOG_COLUMNS)] += 123.0
    changed.loc[future, list(DIGITAL_COLUMNS)] = 1 - changed.loc[future, list(DIGITAL_COLUMNS)]
    recomputed = window_features(changed, _config())

    pd.testing.assert_frame_equal(baseline.loc[:cut], recomputed.loc[:cut], check_exact=True)
    assert not baseline.loc[cut + SEC :].equals(recomputed.loc[cut + SEC :])


def test_no_window_spans_a_segment_gap() -> None:
    df = make_frame()
    df.loc[df["segment_id"] == 1, list(ANALOG_COLUMNS)] += 1000.0
    # a 60 min window would reach back into segment 0 (30 min earlier) if it ignored the gap
    out = window_features(df, _config(windows=("3600s",), min_coverage=0.05))
    seg0, seg1 = out[out["segment_id"] == 0], out[out["segment_id"] == 1]

    assert not seg1.empty
    assert (seg1["TP2__min__3600s"] > 900).all()
    assert (seg0["TP2__max__3600s"] < 900).all()


def test_low_coverage_warmup_rows_are_dropped_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    df = make_frame()
    with caplog.at_level(logging.INFO, logger="railguard"):
        out = window_features(df, _config(windows=("300s",)))

    # A 300 s window at 10 s sampling expects 30 rows; 0.8 coverage needs 24 (230 s in).
    # Segment 0 starts on a minute boundary, so its scoring rows are at +50 s, +110 s, ...
    # Segment 1 starts at :50, so its scoring rows are at +0 s, +60 s, ... and 240 s is the first
    # one with 24 rows or more. Dropped: 3 in segment 0, 4 in segment 1.
    seg_starts = df.groupby("segment_id")[TIMESTAMP_COL].min()
    first_kept = {0: 230 * SEC, 1: 240 * SEC}
    for seg_id, offset in first_kept.items():
        assert out[out["segment_id"] == seg_id].index[0] == seg_starts[seg_id] + offset
    assert len(out) == 121 - 7
    assert "dropped 7 of 121" in caplog.text


@pytest.mark.parametrize(
    "kwargs",
    [
        {"window_sizes": ()},
        {"window_sizes": (pd.Timedelta(0),)},
        {"sample_interval": pd.Timedelta(0)},
        {"stride": pd.Timedelta(0)},
        {"min_coverage": 0.0},
        {"min_coverage": 1.5},
    ],
)
def test_feature_config_rejects_invalid_values(kwargs: dict[str, object]) -> None:
    base: dict[str, object] = {
        "window_sizes": (pd.Timedelta("60s"),),
        "sample_interval": pd.Timedelta("10s"),
        "stride": pd.Timedelta("60s"),
        "min_coverage": 0.8,
    }
    with pytest.raises(ValueError):
        FeatureConfig(**{**base, **kwargs})  # type: ignore[arg-type]


def test_single_row_frame_is_scored_but_thin_windows_are_dropped() -> None:
    out = window_features(_tiny_frame().iloc[:1], _config())

    assert out.empty  # one row cannot reach 80% coverage of a 60 s window


def test_rejects_nan_signals_and_bad_segment_ids() -> None:
    nan_frame = _tiny_frame().assign(TP2=lambda d: d["TP2"].where(d.index != 3))
    with pytest.raises(ValueError, match="NaN"):
        window_features(nan_frame, _config())
    with pytest.raises(ValueError, match="segment_id"):
        window_features(_tiny_frame().assign(segment_id=0.5), _config())


def test_dropout_inside_a_segment_lowers_coverage() -> None:
    df = make_frame()
    seg0 = df["segment_id"] == 0
    gappy = df[~(seg0 & df.index.isin(range(100, 200)))].reset_index(drop=True)
    out = window_features(gappy, _config(windows=("300s",)))
    gap_start = START + 100 * 10 * SEC
    inside = out[
        (out["segment_id"] == 0) & (out.index >= gap_start) & (out.index < gap_start + 4 * 60 * SEC)
    ]

    assert inside.empty  # windows over the hole hold too few rows


def test_coverage_does_not_depend_on_rows_after_the_scoring_time() -> None:
    df = make_frame()
    baseline = window_features(df, _config())
    cut = baseline.index[10]  # inside segment 0
    truncated = window_features(df[df[TIMESTAMP_COL] <= cut], _config())

    pd.testing.assert_frame_equal(baseline.loc[:cut], truncated.loc[:cut], check_exact=True)
