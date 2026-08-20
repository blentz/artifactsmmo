"""The gear gap between a character and a fight it cannot win — as a FACT.

`predict_win` answers "do I beat this monster?" with a bool, and `combat_margin`
answers it with a signed margin. Neither says WHAT TO DO when the answer is no,
so nothing in the bot ever linked a lost fight to the gear that would win it.

What stood in for that link was a countdown: `GOAL_OSCILLATION` recovery put the
losing grind in a penalty box for 5 cycles, then 15, then raised `StuckExit`
(`player.py`). A countdown expires whether or not anything changed, so the loop
could not converge — live on C3P0 (2026-08-20) it re-fought the same pig 42 times,
lost 42 times, and the escalation ladder killed the session rather than fixing the
gear. `combat_loadout_outcome` holds all 42 rows as `(predicted_win=0, actual_win=0)`:
the model was right every time and the bot fought anyway.

`combat_deficit` is that missing link, and it is a fact rather than a timer:

  * `None` exactly when `predict_win` holds — so a caller that suppresses a fight
    "while the deficit is non-None" releases the moment the gear lands, with
    nothing to expire and no escalation to exhaust.
  * otherwise a `CombatDeficit` naming the acquisitions that close the margin,
    each carrying the crafting skill that gates it. C3P0's real chain was
    `iron_sword` -> `iron_armor` -> `earth_boost_potion` -> `earth_ring`
    (margin -10 -> +1), three of the four needing `iron_bar` and every one gated
    behind a skill level it did not have. That is the whole shape of the problem:

        fight deficit <- gear deficit <- skill deficit <- material deficit

    A single-item answer would have hidden three of those four layers.

USER (2026-08-20), on what to do when no one item is enough: "that just means we
need multiple upgrades before we can win that fight. the time it takes is just the
cost of progress." So the chain STACKS rather than giving up, and there is no
fallback to an easier monster.

Greedy on MARGIN, deliberately. The live failure was the opposite: `map_guard`'s
GEAR_REVIEW branch ranked upgrades with a monster-blind `_best_by_value` scan and
chose `iron_boots` — already worn, and absent from all 24 items that improved the
pig margin — while the weapon that actually moved `rounds_to_kill` went unbuilt
for ten hours.

Costs one `combat_margin` per candidate per step. That is fine for the read-only
`combat-deficit` diagnostic; a per-cycle caller must memoize (see
`equipment/loadout_cache.py` for the established read-set-keyed pattern).
"""

import dataclasses
from dataclasses import dataclass

from artifactsmmo_cli.ai.combat import combat_margin, predict_win
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_taxonomy import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.world_state import WorldState

MAX_CHAIN = 8
"""Bound on the greedy walk.

Not a modelling constant — a termination bound. The walk already stops when no
candidate improves the margin; this caps the pathological case where a long tail
of +1 items each improves it without ever closing the gap. C3P0's real chain was
4 steps.
"""


@dataclass(frozen=True)
class DeficitStep:
    """One acquisition in the chain, with the skill gate that stands in front of it.

    `crafting_skill` / `crafting_level` are carried because the gear layer is not
    the bottom of the chain: C3P0 could not craft `iron_sword` at weaponcrafting 6
    however many `iron_bar` it held. A step without its gate reads as actionable
    when it is not.
    """

    code: str
    item_type: str
    item_level: int
    crafting_skill: str | None
    crafting_level: int
    margin_after: int


@dataclass(frozen=True)
class CombatDeficit:
    """Why this fight is lost, and what closes it.

    `closes` distinguishes "unwinnable and I know what to build" from "unwinnable
    and I do not" — a caller that blocks a fight on this fact must be able to tell
    those apart, because only the first one is progress.
    """

    monster: str
    baseline_margin: int
    chain: tuple[DeficitStep, ...]
    closes: bool


def _pool(state: WorldState, game_data: GameData,
          candidates: tuple[str, ...] | None) -> tuple[tuple[str, ItemStats], ...]:
    """Candidate (code, stats) pairs, in catalog order.

    Resolves stats ONCE here rather than in the greedy walk, so a caller-supplied
    code with no catalog entry is dropped at the boundary instead of surfacing as
    a None deep inside the scoring loop.
    """
    if candidates is None:
        return tuple(
            (code, stats)
            for code, stats in game_data.items.stats.items()
            if stats.type_ in ITEM_TYPE_TO_SLOTS and stats.level <= state.level
        )
    resolved = ((code, game_data.item_stats(code)) for code in candidates)
    return tuple((code, stats) for code, stats in resolved if stats is not None)


def _margin_owning(state: WorldState, game_data: GameData, monster: str,
                   inventory: dict[str, int], code: str) -> int:
    """Margin against `monster` if the character also OWNED one `code`.

    Owning, not wearing: `predict_win` / `pick_loadout` already choose the best
    on-hand loadout per monster's resistances, so the honest question for "is this
    worth acquiring" is marginal — the same framing `weapon_winnability` uses.
    """
    trial = dict(inventory)
    trial[code] = trial.get(code, 0) + 1
    return combat_margin(dataclasses.replace(state, inventory=trial), game_data, monster)


def combat_deficit(
    state: WorldState,
    game_data: GameData,
    monster: str,
    candidates: tuple[str, ...] | None = None,
    max_chain: int = MAX_CHAIN,
) -> CombatDeficit | None:
    """The gear gap against `monster`, or None when the fight is already winnable.

    Args:
      state:      the character. Read at its CURRENT hp, exactly as `predict_win`
                  does — a deficit computed at full hp would clear itself every
                  time the character rested.
      game_data:  static world data.
      monster:    monster code.
      candidates: item codes to consider acquiring. Defaults to every equippable
                  at or below the character's level. Injectable so a caller can
                  narrow it to what is actually acquirable (`obtain_sources`)
                  without this core taking a dependency on the acquisition model.
      max_chain:  bound on the greedy walk.
    """
    if predict_win(state, game_data, monster):
        return None
    baseline = combat_margin(state, game_data, monster)
    pool = _pool(state, game_data, candidates)

    inventory = dict(state.inventory)
    chain: list[DeficitStep] = []
    current = baseline
    closes = False
    while len(chain) < max_chain:
        best: tuple[str, ItemStats] | None = None
        best_margin = current
        for code, stats in pool:
            margin = _margin_owning(state, game_data, monster, inventory, code)
            if margin > best_margin:
                best, best_margin = (code, stats), margin
        if best is None:
            break
        best_code, best_stats = best
        inventory[best_code] = inventory.get(best_code, 0) + 1
        current = best_margin
        chain.append(DeficitStep(
            code=best_code,
            item_type=best_stats.type_,
            item_level=best_stats.level,
            crafting_skill=best_stats.crafting_skill,
            crafting_level=best_stats.crafting_level,
            margin_after=current,
        ))
        if predict_win(dataclasses.replace(state, inventory=inventory), game_data, monster):
            closes = True
            break
    return CombatDeficit(monster=monster, baseline_margin=baseline,
                         chain=tuple(chain), closes=closes)
