"""Tests for ``evaluation.event_metrics`` (T-002-09)."""

import pandas as pd
import pytest

from railguard.data.labels import FailureWindow
from railguard.evaluation.alerts import AlertEpisode
from railguard.evaluation.event_metrics import evaluate_events, operating_hours

START = pd.Timestamp("2020-06-01 12:00")
END = START + pd.Timedelta(hours=2)
HORIZON = pd.Timedelta(hours=6)
S = pd.Timedelta(seconds=1)


def _window(wid: int = 1, start: pd.Timestamp = START, end: pd.Timestamp = END) -> FailureWindow:
    return FailureWindow(wid, start, end, "f", "s", None, "")


def _ep(start: pd.Timestamp, end: pd.Timestamp | None = None) -> AlertEpisode:
    return AlertEpisode(start=start, end=end if end is not None else start, peak_score=1.0)


def test_episode_exactly_at_start_minus_horizon_is_detected() -> None:
    result = evaluate_events([_ep(START - HORIZON)], [_window()], HORIZON, 10.0)

    assert result.events[0].detected
    assert result.events[0].lead_time_s == HORIZON.total_seconds()
    assert result.outside_alerts == 0


def test_episode_one_second_before_horizon_is_not_detected() -> None:
    result = evaluate_events([_ep(START - HORIZON - S)], [_window()], HORIZON, 10.0)

    assert not result.events[0].detected
    assert result.events[0].lead_time_s is None
    assert result.events[0].first_alert is None
    assert result.outside_alerts == 1


def test_episode_ending_at_start_minus_horizon_overlaps() -> None:
    ep = _ep(START - HORIZON - 5 * S, START - HORIZON)

    assert evaluate_events([ep], [_window()], HORIZON, 1.0).events[0].detected


def test_episode_after_end_is_outside_windows() -> None:
    result = evaluate_events([_ep(END + S)], [_window()], HORIZON, 4.0)

    assert not result.events[0].detected
    assert result.outside_alerts == 1
    assert result.outside_per_hour == 0.25


def test_lead_time_sign_negative_when_first_alert_after_start() -> None:
    result = evaluate_events([_ep(START + 60 * S)], [_window()], HORIZON, 1.0)

    assert result.events[0].lead_time_s == -60.0
    assert result.events[0].first_alert == START + 60 * S


def test_first_alert_is_earliest_overlapping_episode() -> None:
    eps = [_ep(START - 3600 * S), _ep(START - 60 * S)]
    result = evaluate_events(eps, [_window()], HORIZON, 1.0)

    assert result.events[0].lead_time_s == 3600.0
    assert result.detected == 1


def test_two_events_and_zero_alerts() -> None:
    w2 = _window(2, START + pd.Timedelta(days=5), START + pd.Timedelta(days=5, hours=1))
    result = evaluate_events([], [_window(), w2], HORIZON, 5.0)

    assert result.detected == 0
    assert [e.event_id for e in result.events] == [1, 2]
    assert result.outside_alerts == 0
    assert result.outside_per_hour == 0.0


def test_non_positive_operating_hours_raise() -> None:
    with pytest.raises(ValueError, match="operating"):
        evaluate_events([], [_window()], HORIZON, 0.0)


def test_operating_hours_exclude_gaps() -> None:
    ts = pd.Series(
        pd.to_datetime(
            ["2020-01-01 00:00", "2020-01-01 01:00", "2020-01-02 00:00", "2020-01-02 02:00"]
        )
    )
    ids = pd.Series([0, 0, 1, 1])

    assert operating_hours(ts, ids) == 3.0


def test_operating_hours_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length"):
        operating_hours(pd.Series([START]), pd.Series([0, 1]))


def test_episode_starting_exactly_at_window_end_is_detected_not_outside() -> None:
    result = evaluate_events([_ep(END)], [_window()], HORIZON, 1.0)

    assert result.events[0].detected
    assert result.outside_alerts == 0


def test_operating_hours_nan_segment_ids_raise() -> None:
    ts = pd.Series(pd.to_datetime(["2020-01-01 00:00", "2020-01-01 01:00"]))

    with pytest.raises(ValueError, match="NaN"):
        operating_hours(ts, pd.Series([0.0, float("nan")]))


def test_episode_begun_before_range_is_clamped_to_start_minus_horizon() -> None:
    ep = _ep(START - pd.Timedelta(hours=72), START - pd.Timedelta(hours=1))
    event = evaluate_events([ep], [_window()], HORIZON, 1.0).events[0]

    assert event.detected
    assert event.first_alert == START - HORIZON
    assert event.lead_time_s == HORIZON.total_seconds()


def test_episode_starting_inside_range_keeps_its_start() -> None:
    ep = _ep(START - 2 * HORIZON / 3)
    event = evaluate_events([ep], [_window()], HORIZON, 1.0).events[0]

    assert event.first_alert == ep.start
    assert event.lead_time_s == (2 * HORIZON / 3).total_seconds()


def test_episode_starting_after_start_has_negative_lead_time() -> None:
    event = evaluate_events([_ep(START + 30 * S)], [_window()], HORIZON, 1.0).events[0]

    assert event.lead_time_s == -30.0


def test_earliest_in_range_alert_wins_among_overlapping_episodes() -> None:
    long_ep = _ep(START - pd.Timedelta(hours=72), START - pd.Timedelta(hours=5))
    inside = _ep(START - pd.Timedelta(hours=2))
    event = evaluate_events([long_ep, inside], [_window()], HORIZON, 1.0).events[0]

    assert event.first_alert == START - HORIZON
    assert event.lead_time_s == HORIZON.total_seconds()
