"""Synthetic MetroPT-3-shaped frame for fast, deterministic tests (no CSV needed)."""

import numpy as np
import pandas as pd

from railguard.data.metropt3 import ANALOG_COLUMNS, DIGITAL_COLUMNS, TIMESTAMP_COL

START = pd.Timestamp("2020-03-01")
STEP_S = 10
ROWS_PER_SEGMENT = 360  # one hour at 10 s
GAP = pd.Timedelta(minutes=30)  # time from the last row of segment 0 to the first of segment 1
STEP_COLUMN = "TP2"
STEP_SIZE = 5.0


def make_frame(
    rows_per_segment: int = ROWS_PER_SEGMENT,
    step_at: int | None = ROWS_PER_SEGMENT // 2,
    seed: int = 0,
) -> pd.DataFrame:
    """Two segments sampled every 10 s, separated by ``GAP``.

    Analogue signals are small noise around a constant. ``STEP_COLUMN`` jumps by
    ``STEP_SIZE`` from row ``step_at`` of segment 1 onwards (``None`` disables it).
    Digital signals toggle every 6 rows, so each has a 50% duty cycle.
    Returns the columns ``timestamp``, all signals and ``segment_id``.
    """
    rng = np.random.default_rng(seed)
    frames = []
    seg_start = START
    for segment_id in range(2):
        ts = pd.date_range(seg_start, periods=rows_per_segment, freq=f"{STEP_S}s")
        data: dict[str, object] = {TIMESTAMP_COL: ts}
        for i, col in enumerate(ANALOG_COLUMNS):
            data[col] = 10.0 * (i + 1) + rng.normal(0.0, 0.1, rows_per_segment)
        for col in DIGITAL_COLUMNS:
            data[col] = (np.arange(rows_per_segment) // 6 % 2).astype("int8")
        frame = pd.DataFrame(data)
        if segment_id == 1 and step_at is not None:
            frame.loc[step_at:, STEP_COLUMN] += STEP_SIZE
        frame["segment_id"] = segment_id
        frames.append(frame)
        seg_start = ts[-1] + GAP
    return pd.concat(frames, ignore_index=True)
