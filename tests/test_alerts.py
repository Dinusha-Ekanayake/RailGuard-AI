"""Tests for ``evaluation.alerts.alert_episodes`` (T-002-08)."""

import pandas as pd
import pytest

from railguard.evaluation.alerts import AlertEpisode, alert_episodes

T0 = pd.Timestamp("2020-05-01")
MIN = pd.Timedelta(minutes=1)
GAP = pd.Timedelta(minutes=10)


def _series(values: list[float], offsets_min: list[int]) -> pd.Series:
    return pd.Series(values, index=pd.DatetimeIndex([T0 + o * MIN for o in offsets_min]))


def _segments(scores: pd.Series, ids: list[int]) -> pd.Series:
    return pd.Series(ids, index=scores.index)


def test_alerts_within_merge_gap_form_one_episode() -> None:
    scores = _series([5, 0, 0, 6, 0], [0, 1, 5, 10, 11])
    out = alert_episodes(scores, 1.0, GAP, _segments(scores, [0] * 5))

    assert out == [AlertEpisode(start=T0, end=T0 + 10 * MIN, peak_score=6.0)]


def test_alerts_beyond_merge_gap_split() -> None:
    scores = _series([5, 7], [0, 11])
    out = alert_episodes(scores, 1.0, GAP, _segments(scores, [0, 0]))

    assert [e.start for e in out] == [T0, T0 + 11 * MIN]
    assert [e.peak_score for e in out] == [5.0, 7.0]


def test_gap_equal_to_merge_gap_still_merges() -> None:
    scores = _series([5, 5], [0, 10])

    assert len(alert_episodes(scores, 1.0, GAP, _segments(scores, [0, 0]))) == 1


def test_episodes_never_merge_across_segments() -> None:
    scores = _series([5, 5], [0, 2])  # 2 min apart, well within the merge gap
    out = alert_episodes(scores, 1.0, GAP, _segments(scores, [0, 1]))

    assert len(out) == 2


def test_threshold_is_strict_and_no_alerts_gives_empty_list() -> None:
    scores = _series([1.0, 0.5], [0, 1])

    assert alert_episodes(scores, 1.0, GAP, _segments(scores, [0, 0])) == []
    assert alert_episodes(scores.iloc[0:0], 1.0, GAP, _segments(scores.iloc[0:0], [])) == []


def test_episodes_are_sorted_by_start() -> None:
    scores = _series([5, 0, 5, 0, 5], [0, 1, 30, 31, 60])
    out = alert_episodes(scores, 1.0, GAP, _segments(scores, [0, 0, 1, 1, 2]))

    assert [e.start for e in out] == sorted(e.start for e in out)
    assert len(out) == 3


def test_rejects_mismatched_segment_index() -> None:
    scores = _series([5, 5], [0, 1])
    with pytest.raises(ValueError, match="same index"):
        alert_episodes(scores, 1.0, GAP, pd.Series([0, 0]))


def test_nan_segment_ids_raise() -> None:
    scores = _series([5, 7], [0, 1])
    ids = pd.Series([0.0, float("nan")], index=scores.index)

    with pytest.raises(ValueError, match="NaN"):
        alert_episodes(scores, 1.0, GAP, ids)


def test_duplicated_score_index_raises() -> None:
    scores = _series([5, 7], [0, 0])

    with pytest.raises(ValueError, match="duplicate"):
        alert_episodes(scores, 1.0, GAP, _segments(scores, [0, 0]))
