"""The fight loop's XP rate for one monster and one utility loadout, read from
the world (`docs/PLAN_consumable_utility.md` increment 3). The arithmetic is
`loop_rate_core` (proved: `Formal.LoopRate`) and the fight is
`fight_outcome_core.fight_outcome` (proved: `Formal.FightOutcome`); this module
assembles their inputs. Not wired into any decision yet.

ONE LOOP is a fight from full HP, the recovery back to full, and the price of
what the fight consumed (the steady state of a grind: every fight after the
first starts where the last recovery left it, at full).

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
  terms are built over) with the restore's stock. Its duration is ONE
  `TYPICAL_FIGHT_COOLDOWN_SECONDS` (30 s): the code has no per-round seconds,
  and the fight cooldown it already prices is per fight.
* CONSUMED — the restore potions the walk drank, and one of each boost (the
  increment-0 data: one boost per fight), each at
  `consumable_price.consumable_price_of`. A consumed item with no price makes
  the loop unrunnable: the result is None.
* RECOVERY — `recovery_seconds` of the missing HP (`max_hp − hp_end`, the end
  pool floored to whole HP), over the foods held in the bag or bank, each at its
  price (held: 0), eaten at the flat `CONSUMABLE_COOLDOWN_SECONDS`.
* XP — `game_data.xp_per_kill` at the character's level and wisdom on a win;
  0 on a loss."""

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from artifactsmmo_cli.ai.actions.cost_core import CONSUMABLE_COOLDOWN_SECONDS
from artifactsmmo_cli.ai.boost_selection import project_equip
from artifactsmmo_cli.ai.combat import combat_terms, fight_max_hp
from artifactsmmo_cli.ai.consumable_floor import FOOD, POTION, heal_candidates
from artifactsmmo_cli.ai.consumable_price import FIGHT_SECONDS, consumable_price_of, held_count
from artifactsmmo_cli.ai.fight_outcome_core import fight_outcome
from artifactsmmo_cli.ai.fight_terms_core import SCALE
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loop_rate_core import recovery_seconds, xp_per_second
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.utility_slot import UTILITY_SLOTS
from artifactsmmo_cli.ai.world_state import WorldState

EAT_SECONDS = Fraction(CONSUMABLE_COOLDOWN_SECONDS)
"""One use of a food, whatever the quantity, exact."""

SPLASH_RESTORE = "splash_restore"
"""The API effect of a splash potion: "Restores X HP at the start of the turn to
another character" — `hp_restore` carries its value too, but it never heals the
wearer, so the solo loop refuses it rather than walking it as a restore."""


@dataclass(frozen=True)
class LoopRate:
    """One loop's XP rate and its parts (seconds exact, HP whole)."""

    xp_per_second: Fraction
    xp_per_kill: int
    win: bool
    fight_seconds: Fraction
    recovery_seconds: Fraction
    consumed_seconds: Fraction
    max_hp: int
    hp_end: int
    used: tuple[tuple[str, int], ...]


def held_foods(state: WorldState, game_data: GameData) -> list[str]:
    """The foods held in the bag or bank, in catalogue order."""
    return [code for code in heal_candidates(game_data, FOOD) if held_count(code, state) > 0]


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


def loop_rate(state: WorldState, game_data: GameData, ctx: SelectionContext, monster: str,
              loadout: Sequence[tuple[str, int]],
              store: LearningStore | None = None) -> LoopRate | None:
    """The loop's XP per second against `monster` wearing `loadout` (see the
    module doc); None when something the fight consumes has no price."""
    restore_code, restore_hp, restore_stock = _restore_of(loadout, game_data)
    codes: list[str | None] = [code for code, _ in loadout]
    codes += [None] * (len(UTILITY_SLOTS) - len(codes))
    projected = state
    for slot, code in zip(UTILITY_SLOTS, codes, strict=True):
        projected = project_equip(projected, code, game_data, slot=slot)
    max_hp = fight_max_hp(projected, game_data, monster)
    outcome = fight_outcome(combat_terms(projected, game_data, monster),
                            max_hp, max_hp, restore_hp, restore_stock)
    used = tuple((code, outcome.used if code == restore_code else 1) for code, _ in loadout)
    consumed = Fraction(0)
    for code, n in used:
        if n == 0:
            continue
        price = consumable_price_of(code, state, game_data, ctx, store)
        if price is None:
            return None
        consumed += n * price
    food: list[tuple[int, Fraction]] = []
    for code in held_foods(state, game_data):
        price = consumable_price_of(code, state, game_data, ctx, store)
        assert price is not None  # held stock is free (`consumable_price_of`)
        food.append((game_data.hp_restore_of(code), price))
    hp_end = outcome.hp_end // SCALE
    recovery = recovery_seconds(max_hp - hp_end, max_hp, food, EAT_SECONDS)
    xp = game_data.xp_per_kill(monster, state.level, state.wisdom) if outcome.win else 0
    return LoopRate(xp_per_second(xp, FIGHT_SECONDS, recovery, consumed), xp, outcome.win,
                    FIGHT_SECONDS, recovery, consumed, max_hp, hp_end, used)
