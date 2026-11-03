"""Tests for ``models.baselines`` (T-002-06, T-002-07)."""

import logging

import numpy as np
import pandas as pd
import pytest

from railguard.evaluation.experiment_config import IsolationForestParams
from railguard.models.baselines import IsolationForestScorer, RobustZScore

PARAMS = IsolationForestParams(n_estimators=50, max_samples=64, contamination="auto")


def _normal(rows: int = 300, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"a": rng.normal(0, 1, rows), "b": rng.normal(5, 2, rows)})


def _with_outlier(frame: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([frame, pd.DataFrame({"a": [12.0], "b": [40.0]})], ignore_index=True)


@pytest.mark.parametrize(
    "scorer",
    [RobustZScore(), IsolationForestScorer(PARAMS, seed=1)],
    ids=["zscore", "iforest"],
)
def test_outlier_scores_above_normal_rows(scorer) -> None:  # type: ignore[no-untyped-def]
    train = _normal()
    scorer.fit(train)
    scores = scorer.score(_with_outlier(train))

    assert scores.shape == (len(train) + 1,)
    # Isolation Forest scores saturate outside the training range, so compare with the
    # bulk of normal rows rather than demanding a strict maximum.
    assert scores[-1] > np.quantile(scores[:-1], 0.99)
    if isinstance(scorer, RobustZScore):
        assert scores[-1] > scores[:-1].max()


def test_zscore_matches_hand_computed_value() -> None:
    fit = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 100.0]})  # median 3, MAD 1
    scorer = RobustZScore().fit(fit)
    scores = scorer.score(pd.DataFrame({"a": [3.0, 3.0 + 1.4826 * 2]}))

    assert scores == pytest.approx([0.0, 2.0])


def test_zscore_zero_mad_falls_back_to_std() -> None:
    fit = pd.DataFrame({"a": [1.0, 1.0, 1.0, 1.0, 6.0]})  # MAD 0, std > 0
    scorer = RobustZScore().fit(fit)
    expected = 5.0 / fit["a"].std()

    assert scorer.score(pd.DataFrame({"a": [6.0]}))[0] == pytest.approx(expected)


def test_zscore_constant_feature_is_dropped_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    fit = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0], "const": [7.0] * 5})
    with caplog.at_level(logging.INFO, logger="railguard"):
        scorer = RobustZScore().fit(fit)

    assert "const" in caplog.text
    assert scorer.dropped_features == ("const",)
    # a changed constant feature must not influence the score
    scores = scorer.score(pd.DataFrame({"a": [3.0], "const": [1e9]}))
    assert scores[0] == pytest.approx(0.0)


def test_zscore_all_constant_raises() -> None:
    with pytest.raises(ValueError, match="no usable features"):
        RobustZScore().fit(pd.DataFrame({"a": [1.0] * 4}))


def test_scorers_reject_nan_and_missing_columns_and_unfitted_use() -> None:
    fitted = RobustZScore().fit(_normal())
    with pytest.raises(ValueError, match="NaN"):
        fitted.score(pd.DataFrame({"a": [np.nan], "b": [1.0]}))
    with pytest.raises(ValueError, match="missing"):
        fitted.score(pd.DataFrame({"a": [1.0]}))
    with pytest.raises(ValueError, match="NaN"):
        RobustZScore().fit(pd.DataFrame({"a": [1.0, np.nan]}))
    with pytest.raises(RuntimeError, match="fit"):
        RobustZScore().score(_normal())
    with pytest.raises(RuntimeError, match="fit"):
        IsolationForestScorer(PARAMS, seed=0).score(_normal())


def test_iforest_same_seed_gives_identical_scores_and_other_seed_differs() -> None:
    train, test = _normal(), _with_outlier(_normal(50, seed=3))
    first = IsolationForestScorer(PARAMS, seed=7).fit(train).score(test)
    again = IsolationForestScorer(PARAMS, seed=7).fit(train).score(test)
    other = IsolationForestScorer(PARAMS, seed=8).fit(train).score(test)

    assert np.array_equal(first, again)
    assert not np.array_equal(first, other)


def test_iforest_tolerates_a_constant_feature() -> None:
    train = _normal().assign(const=1.0)
    scores = IsolationForestScorer(PARAMS, seed=0).fit(train).score(train)

    assert np.isfinite(scores).all()
