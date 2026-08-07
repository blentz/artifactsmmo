"""Pure core for the unified progression objective `J`.

Ranks progression candidates — gear roots and the XP trunk alike — by ONE scalar:
cycles to character level 50. Implements `docs/spec_unified_objective/SPEC.md`;
every decision below cites the clause that forces it.

WHY THIS EXISTS. The selector it is built to replace, `branch_pick_pure`, is a
lexicographic pivot, and its docstring says so: "Gear-first until the band's
loadout is adequate; then xp to the next milestone. One boolean pivot — no scalar
competition (the design's core bet)." Its switch is
`band_adequate = winnable AND NOT has_structural_upgrade`, and the second conjunct
is never true against a 50-level catalogue, so the pivot never flips. Measured:
GEAR chosen in 2950 of 2950 cycles, a 13h five-character run gained ZERO character
levels against 7 in the run before it, and the planner reported
`projected_cycles_to_max: "inf"` in all 7967 cycles of both runs. A lexicographic
order returns one extreme point of a Pareto front; ranking on a common currency
lets the trade-off point emerge instead of being legislated.

THE CURRENCY IS ACTIONS. `acquire_cost` and `cycles_to_fifty` are both counts of
executed planner actions (S-010), which is why S-004 may add them. That identity is
not decorative: the projection feeding `cycles_to_fifty` was denominated in SECONDS
until 2026-08-07 and ran ~80x high, and the whole objective would have optimised
against a fiction. See `ai/learning/projections.FIGHT_CYCLES_PER_KILL`.

NOT DONE HERE: this module computes the ranking; it is not yet wired into
`branch_pick_pure`'s seat. Wiring changes live behaviour and is its own step.
"""

from dataclasses import dataclass

TARGET_LEVEL = 50
"""The terminal objective (S-003). Everything else — gear, skills, gold — is
instrumental and enters `J` only through a candidate's projected outcome."""

_BAND_FINITE = 0
_BAND_UNREACHABLE = 1
_BAND_FAILED = 2
"""Rank bands, in precedence order (S-006, S-012). A finite candidate beats every
unreachable one; every non-FAILED candidate beats every FAILED one."""


@dataclass(frozen=True)
class ProgressionCandidate:
    """One ranked option, with its projection already computed by somebody else.

    Fields are exactly S-002's, flattened: `failed` carries the FAILED outcome
    rather than an optional pair, so the whole descriptor stays inside the
    mechanical-extraction subset.

    `reachable_level` is the highest character level the candidate's outcome can
    reach, and `cycles_to_fifty` the projected actions from that outcome to level
    50. Both are meaningless when `failed` is true, and `cycles_to_fifty` is
    additionally meaningless when `reachable_level < TARGET_LEVEL` (S-014) — the
    ordering below never reads a field the spec has declared void.

    There is deliberately NO `kind` field. An earlier draft marked the XP trunk so
    a guard clause could name it; that clause (S-009) was withdrawn as
    self-defeating and redundant, and nothing else ever needed to know which
    candidate was the trunk. The trunk is simply the zero-cost candidate and `J`
    ranks it like any other.
    """
    identity: str
    acquire_cost: int
    reachable_level: int
    cycles_to_fifty: int
    failed: bool


def candidate_band(c: ProgressionCandidate) -> int:
    """Which precedence band `c` sits in (S-012, S-014, S-006).

    Unreachability is decided by the LEVEL FIELD ALONE (S-014). No infinity value
    exists or is permitted as a second encoding, so there is no way for two
    encodings of the same fact to disagree."""
    if c.failed:
        return _BAND_FAILED
    if c.reachable_level < TARGET_LEVEL:
        return _BAND_UNREACHABLE
    return _BAND_FINITE


def objective_j(c: ProgressionCandidate) -> int:
    """`J` — acquisition cost plus the projected cycles remaining to level 50
    (S-004), in one unit (S-010).

    Only meaningful for a finite-band candidate; `sort_key` calls it nowhere
    else."""
    return c.acquire_cost + c.cycles_to_fifty


def sort_key(c: ProgressionCandidate) -> tuple[int, int, int]:
    """The total order, as an integer triple compared lexicographically (S-013:
    exact, no floats, no significance threshold).

    * band — finite < unreachable < FAILED (S-006, S-012).
    * primary — inside the finite band, `J` (S-005). Inside the unreachable band,
      `TARGET_LEVEL - reachable_level`, so a HIGHER reachable level sorts first
      (S-006's furthest-progress key) while staying a non-negative int.
    * secondary — inside the unreachable band, acquisition cost (S-006's second
      key). It is cost and NOT cycles-to-50 because S-014 has just declared that
      figure void for exactly these candidates; ranking on it would compare two
      meaningless numbers.

    FAILED candidates get a constant key: S-012 fixes only that they rank last,
    and imposes no order among them, so they fall through to the caller's
    positional tie-break (S-008) and keep their input order.
    """
    band = candidate_band(c)
    if band == _BAND_FINITE:
        return (band, objective_j(c), 0)
    if band == _BAND_UNREACHABLE:
        return (band, TARGET_LEVEL - c.reachable_level, c.acquire_cost)
    return (band, 0, 0)


def rank_candidates(candidates: list[ProgressionCandidate]) -> list[ProgressionCandidate]:
    """Every candidate given, in rank order, none omitted, duplicated or invented
    (S-007) — including unreachable and FAILED ones.

    Ties are broken by INPUT POSITION, never by comparing identities as text
    (S-008): `sorted` is stable, so equal keys retain their incoming order, and the
    result is reproducible across runs. That also makes the order independent of
    how a caller happens to name its candidates.
    """
    return sorted(candidates, key=sort_key)


def choose(candidates: list[ProgressionCandidate]) -> ProgressionCandidate | None:
    """The chosen candidate: a `J`-minimiser in the finite band, else the furthest
    progress (S-005, S-006), never a FAILED one while any usable candidate exists
    (S-012).

    Returns None for an empty sequence (S-015). That absence means "there was
    nothing to choose between" and is NOT the "could not decide" sentinel S-001
    forbids — which would be a failure report on a NON-empty input, and cannot
    arise here because the order is total.
    """
    if not candidates:
        return None
    return rank_candidates(candidates)[0]
