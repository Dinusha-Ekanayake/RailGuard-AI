import pandas as pd

from railguard.data.metropt3 import ANALOG_COLUMNS, DIGITAL_COLUMNS
from railguard.preprocessing.segments import assign_segments

from .synthetic import GAP, ROWS_PER_SEGMENT, STEP_COLUMN, STEP_S, STEP_SIZE, make_frame


def test_shape_columns_and_segments() -> None:
    df = make_frame()
    assert len(df) == 2 * ROWS_PER_SEGMENT
    assert set(ANALOG_COLUMNS + DIGITAL_COLUMNS) <= set(df.columns)
    assert df["segment_id"].value_counts().to_dict() == {0: ROWS_PER_SEGMENT, 1: ROWS_PER_SEGMENT}


def test_gap_between_segments_and_regular_sampling() -> None:
    df = make_frame()
    diffs = df["timestamp"].diff().dropna()
    assert (diffs == pd.Timedelta(seconds=STEP_S)).sum() == 2 * (ROWS_PER_SEGMENT - 1)
    assert diffs.max() == GAP
    assert assign_segments(df["timestamp"]).tolist() == df["segment_id"].tolist()


def test_step_change_only_in_segment_one() -> None:
    df = make_frame(step_at=100)
    seg1 = df[df["segment_id"] == 1][STEP_COLUMN].to_numpy()
    assert seg1[100:].mean() - seg1[:100].mean() > STEP_SIZE * 0.9
    seg0 = df[df["segment_id"] == 0][STEP_COLUMN]
    assert seg0.max() - seg0.min() < 1.0


def test_deterministic_and_no_step_option() -> None:
    assert make_frame(seed=3).equals(make_frame(seed=3))
    flat = make_frame(step_at=None)[STEP_COLUMN]
    assert (
        flat.groupby(make_frame(step_at=None)["segment_id"])
        .apply(lambda s: s.max() - s.min())
        .max()
        < 1.0
    )
