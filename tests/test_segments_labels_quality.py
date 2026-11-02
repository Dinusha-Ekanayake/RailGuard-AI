import json
from pathlib import Path

import pandas as pd
import pytest

from railguard.data.labels import (
    FAILURE,
    PRE_EVENT,
    UNKNOWN,
    assign_labels,
    load_failure_windows,
)
from railguard.data.metropt3 import DIGITAL_COLUMNS, load_metropt3
from railguard.preprocessing.quality import quality_report
from railguard.preprocessing.segments import assign_segments

T0 = pd.Timestamp("2020-01-01")


def _ts(*offsets_s: int) -> pd.Series:  # type: ignore[type-arg]
    return pd.Series([T0 + pd.Timedelta(seconds=s) for s in offsets_s])


def test_gap_equal_threshold_same_segment() -> None:
    assert assign_segments(_ts(0, 60)).tolist() == [0, 0]


def test_gap_above_threshold_new_segment() -> None:
    assert assign_segments(_ts(0, 61, 71)).tolist() == [0, 1, 1]


def test_empty_input() -> None:
    assert len(assign_segments(pd.Series([], dtype="datetime64[ns]"))) == 0


def test_fixture_two_segments(fixture_csv: Path) -> None:
    df, _ = load_metropt3(fixture_csv)
    assert assign_segments(df["timestamp"]).nunique() == 2


def test_windows_load(windows_yaml: Path) -> None:
    w = load_failure_windows(windows_yaml)
    assert len(w) == 4
    assert all(x.start < x.end for x in w)
    assert "unverified" in (w[1].maintenance or "")


def test_bad_window_rejected(tmp_path: Path) -> None:
    p = tmp_path / "w.yaml"
    p.write_text(
        "windows:\n- {id: 1, start: '2020-01-02', end: '2020-01-01', failure: a, severity: b}\n"
    )
    with pytest.raises(ValueError, match="start must be before end"):
        load_failure_windows(p)


def test_label_boundaries(windows_yaml: Path) -> None:
    w = load_failure_windows(windows_yaml)[3]
    h = pd.Timedelta(hours=1)
    one = pd.Timedelta(seconds=1)
    ts = pd.Series([w.start - h - one, w.start - h, w.start - one, w.start, w.end, w.end + one])
    got = assign_labels(ts, [w], h).astype(str).tolist()
    assert got == [UNKNOWN, PRE_EVENT, PRE_EVENT, FAILURE, FAILURE, UNKNOWN]


def test_overlapping_horizon_failure_wins(windows_yaml: Path) -> None:
    w = load_failure_windows(windows_yaml)
    ts = pd.Series([w[0].start + pd.Timedelta(hours=1), w[1].start - pd.Timedelta(hours=1)])
    got = assign_labels(ts, w, pd.Timedelta(days=60)).astype(str).tolist()
    assert got == [FAILURE, PRE_EVENT]


def test_no_healthy_label(windows_yaml: Path) -> None:
    labels = assign_labels(_ts(0, 10), load_failure_windows(windows_yaml), pd.Timedelta(hours=1))
    assert set(labels.cat.categories) == {FAILURE, PRE_EVENT, UNKNOWN}
    assert labels.astype(str).tolist() == [UNKNOWN, UNKNOWN]


def test_quality_report(fixture_csv: Path) -> None:
    df, _ = load_metropt3(fixture_csv)
    r = quality_report(df, digital_columns=DIGITAL_COLUMNS)
    assert r.rows == 50
    assert r.gap_count == 1
    assert r.interval_seconds["p50"] == 10.0
    assert all(len(v) <= 2 for v in r.digital_cardinality.values())
    assert json.loads(r.to_json())["rows"] == 50
    assert r.to_json() == quality_report(df, digital_columns=DIGITAL_COLUMNS).to_json()


def test_segments_reject_unsorted_and_negative_gap() -> None:
    with pytest.raises(ValueError, match="sorted"):
        assign_segments(_ts(10, 0))
    with pytest.raises(ValueError, match="non-negative"):
        assign_segments(_ts(0, 1), max_gap_s=-1)


def test_segments_custom_threshold_and_index() -> None:
    ts = _ts(0, 10, 200, 210)
    ts.index = pd.Index([5, 6, 7, 8])
    assert assign_segments(ts, max_gap_s=300).tolist() == [0, 0, 0, 0]
    assert assign_segments(ts, max_gap_s=5).tolist() == [0, 1, 2, 3]


def test_negative_horizon_rejected(windows_yaml: Path) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        assign_labels(_ts(0), load_failure_windows(windows_yaml), pd.Timedelta(hours=-1))


def test_duplicate_window_ids_rejected(tmp_path: Path) -> None:
    p = tmp_path / "w.yaml"
    row = "- {id: 1, start: '2020-01-01', end: '2020-01-02', failure: a, severity: b}\n"
    p.write_text("windows:\n" + row + row)
    with pytest.raises(ValueError, match="duplicate"):
        load_failure_windows(p)


def test_window_times_match_spec(windows_yaml: Path) -> None:
    got = [(str(w.start), str(w.end)) for w in load_failure_windows(windows_yaml)]
    assert got == [
        ("2020-04-18 00:00:00", "2020-04-18 23:59:00"),
        ("2020-05-29 23:30:00", "2020-05-30 06:00:00"),
        ("2020-06-05 10:00:00", "2020-06-07 14:30:00"),
        ("2020-07-15 14:30:00", "2020-07-15 19:00:00"),
    ]


def test_quality_report_single_row_is_strict_json(fixture_csv: Path) -> None:
    df, _ = load_metropt3(fixture_csv)
    r = quality_report(df.head(1), digital_columns=DIGITAL_COLUMNS)
    assert json.loads(r.to_json())["interval_seconds"]["p50"] is None
    assert r.gap_count == 0
