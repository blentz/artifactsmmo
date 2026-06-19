"""Shared pure formatters for the TUI plan/log views (no rendering, no state)."""

import re

_OBTAIN_RE = re.compile(r"ObtainItem\(code='([^']+)', quantity=(\d+)\)")


def short_root(root_repr: str) -> str:
    """Collapse an ObtainItem(...) repr to `code` (quantity 1) or `Nx code`.
    Non-ObtainItem reprs are returned unchanged."""
    m = _OBTAIN_RE.fullmatch(root_repr)
    if m is None:
        return root_repr
    code, qty = m.group(1), m.group(2)
    return code if qty == "1" else f"{qty}x {code}"
