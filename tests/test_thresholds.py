"""Tests for ``evaluation.thresholds.select_threshold`` (T-002-10)."""

import logging

import numpy as np
import pandas as pd
import pytest

from railguard.data.labels import FailureWindow
from railguard.evaluation.thresholds import select_threshold

T0 = pd.Timestamp("2020-06-01")
MIN = pd.Timedelta(minutes=1)
HORIZON = pd.Timedelta(hours=1)
MERGE = pd.Timedelta(minutes=2)
N = 1000


def _scores() -> pd.Series:
    # Strictly increasing scores 0..N-1, one row per 10 minutes so each alert is its own episode.
    return pd.Series(
        np.arange(N, dtype=float), index=T0 + pd.to_timedelta(np.arange(N) * 10, "min")
    )


def _call(budget: float, split: str = "validation") -> float:
    scores = _scores()
    return select_threshold(
        scores,
        split,
        [FailureWindow(1, T0 + 100 * 24 * 60 * MIN, T0 + 101 * 24 * 60 * MIN, "f", "s", None, "")],
        HORIZON,
        100.0,
        budget,
        MERGE,
        pd.Series(0, index=scores.index),
    )


@pytest.mark.parametrize("split", ["test", "Test", "TEST", "fit", "outside"])
def test_only_validation_split_is_accepted(split: str) -> None:
    with pytest.raises(ValueError, match="REQ-002-04"):
        _call(1.0, split=split)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_non_finite_scores_raise(bad: float) -> None:
    scores = _scores()
    scores.iloc[3] = bad
    with pytest.raises(ValueError, match="finite"):
        select_threshold(
            scores, "validation", [], HORIZON, 100.0, 1.0, MERGE, pd.Series(0, index=scores.index)
        )


def test_picks_lowest_candidate_within_budget() -> None:
    # Quantile 0.99 leaves ~10 alerts over 100 h = 0.1/h; 0.95 leaves ~50 = 0.5/h.
    threshold = _call(0.1)

    assert threshold == pytest.approx(float(np.quantile(_scores(), 0.99)))


def test_falls_back_to_highest_candidate_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        threshold = _call(0.0)

    assert threshold == pytest.approx(float(np.quantile(_scores(), 0.99999)))
    assert "budget" in caplog.text


def test_empty_scores_raise() -> None:
    empty = pd.Series([], index=pd.DatetimeIndex([]), dtype=float)
    with pytest.raises(ValueError, match="empty"):
        select_threshold(empty, "validation", [], HORIZON, 1.0, 1.0, MERGE, empty.astype(int))


def test_nan_scores_never_yield_nan_threshold() -> None:
    # Adversarial (reviewer): a single NaN score (e.g. a dropped warm-up row) must not
    # silently produce a NaN threshold, which would raise no alerts on any split.
    scores = _scores()
    scores.iloc[0] = np.nan
    try:
        threshold = select_threshold(
            scores, "validation", [], HORIZON, 100.0, 1.0, MERGE, pd.Series(0, index=scores.index)
        )
    except ValueError:
        return
    assert np.isfinite(threshold)
