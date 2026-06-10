"""Differential test: the real Python `pick_winnable_monster_pure` must agree
bit-for-bit with the proved Lean `pickWinnableWindowed` on the
window-preferred-with-liveness-fallback combat-target picker.

The picker (P0 revision, 2026-06-09):

    1. PREFERRED: highest-level winnable monster inside the FightAction
       level window [max(1, char_level-1), char_level+2].
    2. FALLBACK: highest-level winnable monster with xp_per_kill > 0 that
       is under the char_level+2 suicide guard.
    3. None only when nothing winnable grants XP (true combat deadlock).

Hypothesis enumerates catalogs of up to 6 monsters with independent
(level, winnable, xp_positive) attributes. Monster codes on the wire are
the list indices (unique per request, as the oracle's predicate lookup
requires); the Python core uses the stringified index so the comparison
is byte-identical after decoding.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.combat_picker import pick_winnable_monster_pure
from formal.diff.oracle_client import run_oracle

_monster = st.tuples(
    st.integers(min_value=1, max_value=12),   # level
    st.booleans(),                            # winnable
    st.booleans(),                            # xp_positive
)


def _python_pick(char_level: int, catalog: list[tuple[int, bool, bool]]) -> str | None:
    monsters = [(str(k), level) for k, (level, _, _) in enumerate(catalog)]
    winnable = {str(k): w for k, (_, w, _) in enumerate(catalog)}
    xp_pos = {str(k): x for k, (_, _, x) in enumerate(catalog)}
    return pick_winnable_monster_pure(
        char_level,
        monsters,
        lambda code: winnable[code],
        lambda code: xp_pos[code],
    )


@settings(max_examples=400, deadline=None)
@given(
    char_level=st.integers(min_value=1, max_value=10),
    catalog=st.lists(_monster, min_size=0, max_size=6),
)
def test_combat_picker_matches_lean(char_level, catalog) -> None:
    python = _python_pick(char_level, catalog)
    args = [char_level, len(catalog)]
    for k, (level, winnable, xp_pos) in enumerate(catalog):
        args.extend([k, level, int(winnable), int(xp_pos)])
    lean = run_oracle("combat_picker", [args])[0]
    lean_result = lean["result"]
    lean_decoded = None if lean_result is None else str(lean_result)
    assert lean_decoded == python, (
        f"divergence: lean={lean_decoded!r} python={python!r} "
        f"char_level={char_level} catalog={catalog}"
    )


def test_p0_trace_fallback_returns_highest_winnable() -> None:
    """Pin the P0 deadlock repro: level-4 character; chicken (L1) and
    yellow_slime (L2) winnable + XP-positive but below the window [3,6];
    sheep (L5) in window but NOT winnable. The old window-only picker
    returned None forever; the fallback returns yellow_slime (highest
    winnable XP-positive)."""
    catalog = {"chicken": (1, True, True), "yellow_slime": (2, True, True),
               "sheep": (5, False, True)}
    result = pick_winnable_monster_pure(
        4,
        [(code, lvl) for code, (lvl, _, _) in catalog.items()],
        lambda code: catalog[code][1],
        lambda code: catalog[code][2],
    )
    assert result == "yellow_slime"


def test_window_tier_preferred_over_fallback() -> None:
    """A winnable in-window monster wins even when a below-window monster
    is also winnable (the fallback is never consulted)."""
    catalog = {"chicken": (1, True, True), "wolf": (4, True, True)}
    result = pick_winnable_monster_pure(
        5,
        [(code, lvl) for code, (lvl, _, _) in catalog.items()],
        lambda code: catalog[code][1],
        lambda code: catalog[code][2],
    )
    assert result == "wolf"


def test_fallback_respects_suicide_guard() -> None:
    """The fallback never returns a monster above char_level + 2 even if it
    is winnable and XP-positive — FightAction's upper bound would reject it
    (picker-applicability consistency)."""
    catalog = {"chicken": (1, True, True), "ogre": (9, True, True)}
    result = pick_winnable_monster_pure(
        4,
        [(code, lvl) for code, (lvl, _, _) in catalog.items()],
        lambda code: catalog[code][1],
        lambda code: catalog[code][2],
    )
    assert result == "chicken"


def test_fallback_requires_positive_xp() -> None:
    """A winnable below-window monster with ZERO xp is not a target — when
    it is the only winnable monster, the picker honestly returns None
    (true deadlock: gear progression is the only path)."""
    catalog = {"chicken": (1, True, False)}
    result = pick_winnable_monster_pure(
        11,
        [(code, lvl) for code, (lvl, _, _) in catalog.items()],
        lambda code: catalog[code][1],
        lambda code: catalog[code][2],
    )
    assert result is None


def test_empty_catalog_returns_none() -> None:
    assert pick_winnable_monster_pure(
        4, [], lambda _code: True, lambda _code: True) is None
