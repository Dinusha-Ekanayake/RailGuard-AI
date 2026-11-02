"""Dataset provenance metadata and file checksums."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_CHUNK_BYTES = 1 << 20


@dataclass(frozen=True)
class DatasetMetadata:
    name: str
    path: str
    sha256: str
    rows: int
    columns: tuple[str, ...]
    loaded_at: str

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_file(path: str | Path) -> str:
    """Return the hex SHA-256 of a file, streaming it in chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
