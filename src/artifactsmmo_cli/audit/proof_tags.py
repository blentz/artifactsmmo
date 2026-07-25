"""Parse `-- @concept: ... @property: ...` header tags from Lean modules and build
the inverse proof→concept index. Pure (operates on text + name sets); the live
file-walk wrapper lives in scripts/. Mechanically tying each proof to the game
concept(s) it models is what makes the traceability checked, not prose."""

import re
from dataclasses import dataclass

_ALLOWED_PROPERTIES = frozenset({
    "dominance", "monotonicity", "totality", "no-deadlock", "safety", "reachability",
    "liveness", "deduction-accounting",
    # C1–C3 additions: validity (function mirrors a spec), sufficiency (condition
    # guarantees an outcome), termination (process/descent terminates).
    "validity", "sufficiency", "termination",
    # boundedness: the modelled quantity is confined to a stated interval.
    # Distinct from monotonicity (how it MOVES) and from safety (what must never
    # happen). Formal/Synergy.lean is the case — synergy_ge_floor /
    # synergy_le_one / synergy_floor_pos pin synergyPure into [sMin, 1].
    "boundedness",
    # conservation: a modelled quantity is neither minted nor destroyed by a
    # transition — what goes in comes back out. Formal/EscrowConservation.lean is
    # the case: sell_post_cancel_restores / buy_post_cancel_restores return
    # exactly what post locked, and the *_escrow_freed pair shows a fill moves
    # value between ledger columns rather than creating it. Distinct from
    # deduction-accounting (a deduction is BOOKED correctly) and from safety
    # (a state is never REACHED): conservation is an equality across a step.
    "conservation",
    # fail-closed: absent an input the model REFUSES to act, rather than acting on
    # a default. Formal/GePostPricing.lean is the case — with no live anchor the
    # posted price is `none` (sell_none_of_no_anchor / buy_none_of_no_anchor), so
    # an empty order book can never produce a speculative post. Distinct from
    # safety (a bad state is unreachable): this is about the ABSENCE of input.
    "fail-closed",
})
_TAG_RE = re.compile(r"@concept:\s*([^@]+?)\s*@property:\s*(.+)")


@dataclass(frozen=True)
class ProofTags:
    concepts: list[str]
    properties: list[str]


@dataclass(frozen=True)
class IndexRow:
    module: str
    concepts: list[str]
    properties: list[str]


def _split(csv: str) -> list[str]:
    return [tok.strip() for tok in csv.split(",") if tok.strip()]


def parse_tags(text: str) -> ProofTags | None:
    """Return the first `@concept/@property` header in `text`, or None if absent.
    Raises ValueError on an unknown property token (truthfulness over silence)."""
    m = _TAG_RE.search(text)
    if m is None:
        return None
    concepts = _split(m.group(1))
    properties = _split(m.group(2))
    for p in properties:
        if p not in _ALLOWED_PROPERTIES:
            raise ValueError(f"unknown property tag: {p!r} (allowed: {sorted(_ALLOWED_PROPERTIES)})")
    return ProofTags(concepts=concepts, properties=properties)


def build_index(module_tags: dict[str, ProofTags]) -> list[IndexRow]:
    """Inverse index: one row per module → concepts + properties, sorted by module."""
    return [
        IndexRow(module=name, concepts=t.concepts, properties=t.properties)
        for name, t in sorted(module_tags.items())
    ]


def render_index_markdown(rows: list[IndexRow]) -> str:
    lines = [
        "# Proof → concept index (generated — do not hand-edit)",
        "",
        "Inverse of the MATRIX proof-coverage column. Regenerate with",
        "`uv run python scripts/gen_proof_concept_index.py`. A module with no",
        "concept tag, or a concept with no module, is a traceability gap.",
        "",
        "| Module | Concepts | Properties |",
        "|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r.module} | {', '.join(r.concepts)} | {', '.join(r.properties)} |")
    return "\n".join(lines) + "\n"


def cross_check(tagged: set[str], manifest_modules: set[str]) -> list[str]:
    """Every module whose theorems are in Manifest.lean must carry tags. Returns a
    list of human-readable errors (empty = clean)."""
    return [
        f"module in Manifest but untagged (no @concept/@property): {m}"
        for m in sorted(manifest_modules - tagged)
    ]
