"""Pure core for `Player._winnable_farm_target` (`ai/player.py`).

The three-tier cascade that picks which monster the combat-driving goals
should target each cycle:

  1. `task_monster` — the active task's monster (already gated by
     `task_decision == PURSUE` upstream, so a borderline-margin task
     monster is still picked here intentionally).
  2. `path_monster` IF `path_winnable` — the cheapest-path-to-max-level
     next-monster recommendation, accepted only when the runtime
     beatability predictor (stat math + observed-loss veto) agrees.
  3. `pick_winnable` — the highest-level monster the beatability
     predictor accepts, used both when there is no path recommendation
     and when the path recommendation failed the winnable check.

The decision is total (always returns a value, possibly `None`) and is
the EXACT precedence used by the production planner to retarget combat.
The Lean module `formal/Formal/WinnableCascade.lean` proves the
precedence laws, totality, and the no-veto property: if `task_monster`
fires, the winnable check is BYPASSED (intentional, by design).
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
      1. `task_monster` if set (winnable check INTENTIONALLY bypassed).
      2. `path_monster` if set AND `path_winnable`.
      3. `pick_winnable` (may itself be `None` if nothing is winnable).
    """
    if inputs.task_monster is not None:
        return inputs.task_monster
    if inputs.path_monster is not None and inputs.path_winnable:
        return inputs.path_monster
    return inputs.pick_winnable
