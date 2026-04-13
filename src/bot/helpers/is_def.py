from typing import TypeVar

T = TypeVar("T")


def is_def(value: T | None) -> bool:
    """Type-narrowing check for non-None values. Use instead of `val is not None`."""
    return value is not None
