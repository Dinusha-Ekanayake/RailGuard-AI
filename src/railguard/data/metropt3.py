"""MetroPT-3 loader and schema validation (read-only on the raw file)."""

from pathlib import Path

import pandas as pd

from railguard.data.errors import ChecksumMismatchError, SchemaValidationError
from railguard.data.metadata import DatasetMetadata, sha256_file
from railguard.logging_utils import log_rows

TIMESTAMP_COL = "timestamp"
# `DV_eletric` is misspelt in the source; the name is kept on purpose.
ANALOG_COLUMNS: tuple[str, ...] = (
    "TP2",
    "TP3",
    "H1",
    "DV_pressure",
    "Reservoirs",
    "Oil_temperature",
    "Motor_current",
)
DIGITAL_COLUMNS: tuple[str, ...] = (
    "COMP",
    "DV_eletric",
    "Towers",
    "MPG",
    "LPS",
    "Pressure_switch",
    "Oil_level",
    "Caudal_impulses",
)
SCHEMA: dict[str, str] = {
    **dict.fromkeys(ANALOG_COLUMNS, "float32"),
    **dict.fromkeys(DIGITAL_COLUMNS, "int8"),
}
_DATASET_NAME = "MetroPT-3"


def load_metropt3(
    path: str | Path, expected_sha256: str | None = None
) -> tuple[pd.DataFrame, DatasetMetadata]:
    """Load the raw CSV unchanged on disk; drop the unnamed index and parse timestamps.

    Raises ChecksumMismatchError if ``expected_sha256`` is given and differs.
    """
    file_path = Path(path)
    actual = sha256_file(file_path)
    if expected_sha256 is not None and actual != expected_sha256.lower():
        raise ChecksumMismatchError(str(file_path), expected_sha256, actual)

    raw = pd.read_csv(file_path)
    rows_in = len(raw)
    unnamed = [c for c in raw.columns if str(c).startswith("Unnamed")]
    df = raw.drop(columns=unnamed)
    if TIMESTAMP_COL not in df.columns:
        raise SchemaValidationError(TIMESTAMP_COL, "missing")
    df[TIMESTAMP_COL] = pd.to_datetime(df[TIMESTAMP_COL], errors="coerce")
    _cast_numeric(df)
    log_rows("load_metropt3", rows_in, len(df))

    metadata = DatasetMetadata(
        name=_DATASET_NAME,
        path=str(file_path),
        sha256=actual,
        rows=len(df),
        columns=tuple(df.columns),
        loaded_at=DatasetMetadata.now(),
    )
    return df, metadata


def _cast_numeric(df: pd.DataFrame) -> None:
    """Cast known columns in place (analogue to float32, a deliberate precision trade-off)."""
    for column, dtype in SCHEMA.items():
        if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
            continue
        if dtype == "int8" and not df[column].isin([0, 1]).all():
            continue
        df[column] = df[column].astype(dtype)  # type: ignore[call-overload]


def validate_metropt3(df: pd.DataFrame) -> None:
    """Raise SchemaValidationError naming the offending column on the first violation."""
    for column in (TIMESTAMP_COL, *SCHEMA):
        if column not in df.columns:
            raise SchemaValidationError(column, "missing")
    _validate_timestamps(df[TIMESTAMP_COL])
    for column in SCHEMA:
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise SchemaValidationError(column, f"non-numeric dtype {df[column].dtype}")
        if df[column].isna().any():
            raise SchemaValidationError(column, "null values")
    for column in DIGITAL_COLUMNS:
        if not df[column].isin([0, 1]).all():
            raise SchemaValidationError(column, "digital values must be in {0, 1}")


def _validate_timestamps(ts: pd.Series) -> None:
    if not pd.api.types.is_datetime64_any_dtype(ts) or ts.isna().any():
        raise SchemaValidationError(TIMESTAMP_COL, "unparseable timestamps")
    if ts.duplicated().any():
        raise SchemaValidationError(TIMESTAMP_COL, "duplicate timestamps")
    if not ts.is_monotonic_increasing:
        raise SchemaValidationError(TIMESTAMP_COL, "not sorted ascending")
