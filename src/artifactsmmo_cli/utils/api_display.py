"""Helpers for rendering API-sourced fields without fabricating data.

Display commands must not substitute a plausible-looking value (level 0,
gold 0, "") when an API field is absent — that masks contract drift behind
data that reads as real. Render an explicit marker instead.
"""

from artifactsmmo_api_client.types import Unset

MISSING = "—"
"""Shown in place of an API field that is absent or UNSET."""

_SENTINEL = object()


def display_field(obj: object, field: str) -> object:
    """Return obj.<field> for display, or MISSING if absent / UNSET / None.

    Use only for rendering. If a value feeds arithmetic or control flow, read
    it directly so missing data fails loudly rather than turning into a string.
    """
    val = getattr(obj, field, _SENTINEL)
    if val is _SENTINEL or val is None or isinstance(val, Unset):
        return MISSING
    return val
