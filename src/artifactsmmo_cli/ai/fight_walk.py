"""One fight from full HP wearing a utility-potion loadout, and the loadouts
the two utility slots can wear (`docs/PLAN_consumable_utility.md` increments
3-4). Below the pricing: the walk reads no price, so the drop route's WINNABLE
gate can ask it without a cycle through the obtain model
(`loadout_win.wins_with_a_loadout`).

* THE LOADOUT is what the two utility slots wear for the fight — up to two
  `(code, stock)` utility potions, at most one of them a `restore` (the turn walk
  models one restore stock; two different restores would fire in the same turn).
  A `splash_restore` potion heals another character and is refused.
  Each slot is projected through `boost_selection.project_equip`, the path the
  boost choice already uses, and a slot the loadout leaves empty is emptied, so
  "no potions" really is no potions (`combat_terms` would otherwise pick a bag
  boost into the slot).
* THE FIGHT — `combat.combat_terms` over the projected state, walked by
  `fight_outcome` from the projected max HP (`combat.fight_max_hp`, the max the
  terms are built over) with the restore's stock."""

from collections.abc import Sequence

from artifactsmmo_cli.ai.boost_selection import project_equip
from artifactsmmo_cli.ai.combat import combat_terms, fight_max_hp
from artifactsmmo_cli.ai.fight_outcome_core import FightOutcome, fight_outcome
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.heal_catalog import POTION
from artifactsmmo_cli.ai.utility_slot import UTILITY_SLOTS
from artifactsmmo_cli.ai.world_state import WorldState

RESTORE = "restore"
"""The API effect of a self-heal utility potion (increment-0 table)."""

BOOST_PREFIX = "boost_"
"""The API effects of a stat-buff utility potion (`boost_dmg_*`, `boost_res_*`,
`boost_hp`)."""

SPLASH_RESTORE = "splash_restore"
"""The API effect of a splash potion: "Restores X HP at the start of the turn to
another character" — `hp_restore` carries its value too, but it never heals the
wearer, so the solo loop refuses it rather than walking it as a restore."""


def potion_effects_usable(codes: Sequence[str]) -> bool:
    """Every effect changes the wearer's own fight: a `restore` or a boost."""
    return bool(codes) and all(c == RESTORE or c.startswith(BOOST_PREFIX) for c in codes)


def loadouts(candidates: Sequence[str], game_data: GameData) -> list[tuple[str, ...]]:
    """No potions, each candidate, then each pair with at most one restore."""
    out: list[tuple[str, ...]] = [()]
    out += [(code,) for code in candidates]
    for i, first in enumerate(candidates):
        for second in candidates[i + 1:]:
            restores = sum(RESTORE in game_data.effect_codes(c) for c in (first, second))
            if restores <= 1:
                out.append((first, second))
    return out


def _restore_of(loadout: Sequence[tuple[str, int]], game_data: GameData) -> tuple[str | None, int, int]:
    """`(code, restore HP, stock)` of the loadout's restore potion, `(None, 0, 0)`
    without one. Raises on a loadout the slots cannot wear."""
    if len(loadout) > len(UTILITY_SLOTS):
        raise ValueError(f"{len(loadout)} utility potions for {len(UTILITY_SLOTS)} slots")
    if len({code for code, _ in loadout}) != len(loadout):
        raise ValueError(f"one code per utility slot: {loadout}")
    restore: tuple[str | None, int, int] = (None, 0, 0)
    for code, stock in loadout:
        stats = game_data.item_stats(code)
        if stats is None or stats.type_ != POTION:
            raise ValueError(f"{code} is not a utility potion")
        if stock < 1:
            raise ValueError(f"{code} needs a stock of at least 1, got {stock}")
        if SPLASH_RESTORE in game_data.effect_codes(code):
            raise ValueError(f"{code} restores ANOTHER character: no effect in a solo fight")
        if stats.hp_restore > 0:
            if restore[0] is not None:
                raise ValueError(f"two restore potions {restore[0]}, {code}: the walk models one")
            restore = (code, stats.hp_restore, stock)
    return restore


def fight_walk(state: WorldState, game_data: GameData, monster: str,
               loadout: Sequence[tuple[str, int]]) -> tuple[FightOutcome, int, str | None]:
    """The fight from full HP wearing `loadout` (see the module doc's THE
    LOADOUT and THE FIGHT): its outcome, the projected max HP, and the
    loadout's restore potion (None without one)."""
    restore_code, restore_hp, restore_stock = _restore_of(loadout, game_data)
    codes: list[str | None] = [code for code, _ in loadout]
    codes += [None] * (len(UTILITY_SLOTS) - len(codes))
    projected = state
    for slot, code in zip(UTILITY_SLOTS, codes, strict=True):
        projected = project_equip(projected, code, game_data, slot=slot)
    max_hp = fight_max_hp(projected, game_data, monster)
    outcome = fight_outcome(combat_terms(projected, game_data, monster),
                            max_hp, max_hp, restore_hp, restore_stock)
    return outcome, max_hp, restore_code
