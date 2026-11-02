"""CLI: load and validate MetroPT-3, write the quality JSON and processed Parquet."""

import argparse
import logging
from pathlib import Path

import pandas as pd

from railguard.data.labels import assign_labels, load_failure_windows
from railguard.data.metropt3 import DIGITAL_COLUMNS, load_metropt3, validate_metropt3
from railguard.preprocessing.quality import quality_report
from railguard.preprocessing.segments import assign_segments


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--parquet-out", type=Path, required=True)
    parser.add_argument("--sha256", default=None)
    parser.add_argument("--max-gap-s", type=float, default=60.0)
    parser.add_argument("--pre-event-hours", type=float, default=24.0)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    df, _ = load_metropt3(args.csv, args.sha256)
    validate_metropt3(df)
    report = quality_report(df, digital_columns=DIGITAL_COLUMNS, gap_threshold_s=args.max_gap_s)
    df["segment_id"] = assign_segments(df["timestamp"], args.max_gap_s)
    df["label"] = assign_labels(
        df["timestamp"],
        load_failure_windows(args.windows),
        pd.Timedelta(hours=args.pre_event_hours),
    )
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.parquet_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(report.to_json(), encoding="utf-8")
    df.to_parquet(args.parquet_out, index=False)


if __name__ == "__main__":
    main()
