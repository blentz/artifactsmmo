"""Pure core for `Player._pick_winnable_monster` (`ai/player.py`).

Window-preferred combat-target selection with a liveness fallback:

  1. PREFERRED: the highest-level winnable monster inside the FightAction
     level window ``[max(1, char_level - 1), char_level + 2]``.
  2. FALLBACK: when no winnable monster sits in the window, the
     highest-level winnable monster that still grants XP
     (``xp_per_kill > 0`` — the documented XP curve zeroes out at
     ``char_level - monster_level >= 10``) and is not above the
     ``char_level + 2`` suicide guard. This breaks the P0 no-combat
     deadlock (2026-06-09 live repro): a level-4 character whose only
     stat-winnable monsters are chicken (L1) and yellow_slime (L2) must
     grind those rather than never fight at all.
  3. ``None``: nothing winnable grants XP — a true combat deadlock; gear
     progression is the only remaining path (which is correct).

`FightAction.is_applicable` uses the SAME lower gate (``xp_per_kill > 0``)
and the same ``char_level + 2`` upper bound, so every target this picker
returns is level-applicable. The decision is mirrored by the proved Lean
model `formal/Formal/CombatTargetExistence.lean` (`pickWinnableWindowed`)
and diff-locked by `formal/diff/test_combat_picker_diff.py`.

The winnability / XP predicates are passed as callables (mirroring the
Lean model's abstract `WinnableFn`) so the expensive `is_winnable`
evaluation stays lazy: the window tier only probes in-window monsters and
the fallback tier only probes XP-positive ones.
"""
from collections.abc import Callable, Sequence


def pick_winnable_monster_pure(
    char_level: int,
    monsters: Sequence[tuple[str, int]],
    is_winnable: Callable[[str], bool],
    xp_positive: Callable[[str], bool],
) -> str | None:
    """Return the combat target per the window-preferred-with-fallback rule.

    ``monsters`` is the catalog as ``(code, level)`` pairs in iteration
    order; level ties keep the EARLIER entry (matches the Lean left-fold).
    """
    min_level = max(1, char_level - 1)
    max_level = char_level + 2
    best: tuple[str, int] | None = None
    for code, level in monsters:
        if not (min_level <= level <= max_level):
            continue
        if not is_winnable(code):
            continue
        if best is None or level > best[1]:
            best = (code, level)
    if best is not None:
        return best[0]
    for code, level in monsters:
        if level > max_level or not xp_positive(code) or not is_winnable(code):
            continue
        if best is None or level > best[1]:
            best = (code, level)
    return best[0] if best is not None else None
