"""Anchor matching for the mutation gate.

A mutation is pinned to a literal source excerpt (the "anchor"). Applying it used
to be `str.replace(old, new, 1)`, which conflated three distinct situations:

* the anchor appears exactly once   -- the only healthy case;
* the anchor appears several times  -- silently mutated the first occurrence,
  so the mutant could be killed for the wrong reason, or by the wrong test;
* the anchor appears zero times     -- reported as stale, even when the code was
  merely re-indented and the mutant is still perfectly applicable.

This module separates them. Matching is tried in two passes:

1. **Exact substring.** Preserves the historical semantics byte for byte. If the
   anchor occurs exactly once, that is the match.
2. **Reflow-tolerant, line based.** Only if pass 1 found nothing. The anchor and
   each candidate window are stripped of their common leading indentation and
   compared line by line, so re-indenting a block (a new `if`, a class move, a
   formatter pass) no longer reads as a missing anchor. Because the comparison is
   whole-line, an anchor can never match inside a comment or a longer expression
   -- which the old substring search could do.

Both passes require **exactly one** match. Zero raises `AnchorNotFound`; more
than one raises `AnchorAmbiguous`. Neither is silently repaired: an ambiguous
anchor means the gate can no longer say which line it is testing, and that must
be fixed by a human, not guessed at.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class AnchorError(Exception):
    """Base for anchor resolution failures."""


class AnchorNotFound(AnchorError):
    """The anchor matched nothing, under either pass."""


class AnchorAmbiguous(AnchorError):
    """The anchor matched more than once, so the target is undetermined."""


class MatchKind(enum.Enum):
    """How the anchor was resolved. REFLOWED is worth surfacing: it means the
    source moved and the anchor text should be refreshed at leisure, even though
    the mutation still applies."""

    EXACT = "exact"
    REFLOWED = "reflowed"


@dataclass(frozen=True)
class AnchorMatch:
    """Where an anchor resolved to. `start`/`end` are character offsets into the
    source; `indent` is the leading whitespace actually found at the match site,
    which the replacement is re-indented to."""

    start: int
    end: int
    indent: str
    kind: MatchKind


def _common_indent(lines: list[str]) -> str:
    """Longest leading-whitespace prefix shared by every non-blank line."""
    prefixes = [ln[: len(ln) - len(ln.lstrip())] for ln in lines if ln.strip()]
    if not prefixes:
        return ""
    common = prefixes[0]
    for p in prefixes[1:]:
        while not p.startswith(common):
            common = common[:-1]
            if not common:
                return ""
    return common


def _dedent(lines: list[str]) -> list[str]:
    indent = _common_indent(lines)
    if not indent:
        return list(lines)
    return [ln[len(indent):] if ln.strip() else ln.strip() for ln in lines]


def _line_offsets(source: str) -> list[int]:
    """Character offset at which each line of `source` begins."""
    offsets = [0]
    for i, ch in enumerate(source):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


def _find_exact(source: str, anchor: str) -> list[tuple[int, int]]:
    hits: list[tuple[int, int]] = []
    start = source.find(anchor)
    while start != -1:
        hits.append((start, start + len(anchor)))
        start = source.find(anchor, start + 1)
    return hits


def _find_reflowed(source: str, anchor: str) -> list[tuple[int, int, str]]:
    """Whole-line match ignoring the block's own indentation.

    Returns (start, end, indent) per hit. A window matches when, after removing
    the window's common indent, its lines equal the dedented anchor lines.
    """
    anchor_lines = _dedent(anchor.split("\n"))
    if not anchor_lines:
        return []
    src_lines = source.split("\n")
    offsets = _line_offsets(source)
    span = len(anchor_lines)
    hits: list[tuple[int, int, str]] = []
    for i in range(len(src_lines) - span + 1):
        window = src_lines[i : i + span]
        indent = _common_indent(window)
        if _dedent(window) != anchor_lines:
            continue
        start = offsets[i]
        end = offsets[i] + sum(len(ln) + 1 for ln in window) - 1
        hits.append((start, end, indent))
    return hits


def find_anchor(source: str, anchor: str) -> AnchorMatch:
    """Resolve `anchor` in `source` to exactly one site.

    Raises `AnchorNotFound` if it matches nothing and `AnchorAmbiguous` if it
    matches more than once. Ambiguity is an error rather than a first-hit
    fallback: a mutation whose target is undetermined proves nothing.
    """
    exact = _find_exact(source, anchor)
    if len(exact) == 1:
        start, end = exact[0]
        line_start = source.rfind("\n", 0, start) + 1
        lead = source[line_start:start]
        indent = lead if not lead.strip() else ""
        return AnchorMatch(start, end, indent, MatchKind.EXACT)
    if len(exact) > 1:
        raise AnchorAmbiguous(
            f"anchor matched {len(exact)} times exactly; it must match once. "
            f"Anchor:\n{anchor}"
        )

    reflowed = _find_reflowed(source, anchor)
    if len(reflowed) == 1:
        start, end, indent = reflowed[0]
        return AnchorMatch(start, end, indent, MatchKind.REFLOWED)
    if len(reflowed) > 1:
        raise AnchorAmbiguous(
            f"anchor matched {len(reflowed)} times after re-indent normalisation; "
            f"it must match once. Anchor:\n{anchor}"
        )
    raise AnchorNotFound(f"anchor matched nothing. Anchor:\n{anchor}")


def _reindent(text: str, indent: str) -> str:
    lines = _dedent(text.split("\n"))
    return "\n".join(indent + ln if ln.strip() else ln for ln in lines)


def apply_anchor(source: str, old: str, new: str) -> str:
    """Replace the single occurrence of `old` with `new`.

    On an exact match the replacement is spliced verbatim, so behaviour is
    identical to the historical `str.replace(old, new, 1)`. On a reflowed match
    the replacement is re-indented to the indentation actually found at the site,
    so a mutation still applies cleanly to code that has moved.
    """
    match = find_anchor(source, old)
    if match.kind is MatchKind.EXACT:
        replacement = new
    else:
        replacement = _reindent(new, match.indent)
    return source[: match.start] + replacement + source[match.end :]
