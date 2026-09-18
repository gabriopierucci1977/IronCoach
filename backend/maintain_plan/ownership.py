"""Normative subject ownership primitives for MAINTAIN_PLAN artifacts."""

from __future__ import annotations


def subject_ref_errors(value: object, *, field: str = "subject_ref") -> tuple[str, ...]:
    """Validate an opaque subject reference without altering its representation."""
    if type(value) is not str:
        return (f"{field} must be an explicit string",)
    if not value or value.isspace():
        return (f"{field} must be non-empty",)
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return (f"{field} must be valid UTF-8",)
    return ()


def require_subject_ref(value: object, *, field: str = "subject_ref") -> str:
    """Return an unchanged valid subject reference or fail closed."""
    errors = subject_ref_errors(value, field=field)
    if errors:
        raise ValueError(errors[0])
    return value
