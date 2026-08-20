"""Pure core for `Player._winnable_farm_target` (`ai/player.py`).

The three-tier cascade that picks which monster the combat-driving goals
should target each cycle:

  1. `task_monster` — the active task's monster. The SUPPLIER
     (`Player._task_aligned_monster`) is what guarantees this is
     winnable; see the note below.
  2. `path_monster` IF `path_winnable` — the cheapest-path-to-max-level
     next-monster recommendation, accepted only when the runtime
     beatability predictor (stat math + observed-loss veto) agrees.
  3. `pick_winnable` — the highest-level monster the beatability
     predictor accepts, used both when there is no path recommendation
     and when the path recommendation failed the winnable check.

The decision is total (always returns a value, possibly `None`) and is
the EXACT precedence used by the production planner to retarget combat.
The Lean module `formal/Formal/WinnableCascade.lean` proves the
precedence laws and totality.

WHERE THE WINNABLE CHECK LIVES (corrected 2026-08-20). Tier 1 does not
test winnability, and this module used to call that "intentional, by
design", justified by "a persistent loss loop is caught by the
stuck/recovery backstop". It is not: that backstop's remedy is a
COUNTDOWN that expires whether or not anything changed, and its terminal
rung raises `StuckExit`. Live, C3P0 went 0 wins / 42 losses against its
task pig and the ladder killed the run.

The cascade itself was never the defect and `task_wins` was never wrong —
"a supplied task monster wins" is exactly the precedence intended. The
SUPPLIER was wrong. `Player._task_aligned_monster` now applies
`_is_winnable` before supplying one, so this function's contract is
unchanged and its proofs stand as written.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CascadeInputs:
    """Minimal projection of `Player` state used by the cascade."""

    task_monster: str | None
    path_monster: str | None
    path_winnable: bool
    pick_winnable: str | None


def winnable_farm_target_pure(inputs: CascadeInputs) -> str | None:
    """Return the next combat target per the documented 3-tier cascade.

    Precedence (highest first):
      1. `task_monster` if set (its winnability is the SUPPLIER's
         guarantee — see the module docstring).
      2. `path_monster` if set AND `path_winnable`.
      3. `pick_winnable` (may itself be `None` if nothing is winnable).
    """
    if inputs.task_monster is not None:
        return inputs.task_monster
    if inputs.path_monster is not None and inputs.path_winnable:
        return inputs.path_monster
    return inputs.pick_winnable
