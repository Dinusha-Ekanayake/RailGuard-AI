"""Typed errors raised by dataset loading and validation."""


class ChecksumMismatchError(Exception):
    """The file's SHA-256 does not match the expected value."""

    def __init__(self, path: str, expected: str, actual: str) -> None:
        super().__init__(f"SHA-256 mismatch for {path}: expected {expected}, got {actual}")
        self.path = path
        self.expected = expected
        self.actual = actual


class SchemaValidationError(Exception):
    """A column violates the documented schema."""

    def __init__(self, column: str, reason: str) -> None:
        super().__init__(f"column '{column}': {reason}")
        self.column = column
        self.reason = reason
