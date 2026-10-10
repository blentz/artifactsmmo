"""The fleet's consumable floor from live data, rebuilt on the chosen loadouts
(`docs/PLAN_consumable_utility.md` increment 4). The share is the proved pure
core `consumable_floor_core.share`; this module reads its inputs.

USER 2026-10-07: "Fishing feeds Cooking, Cooking feeds HP recovery or provides
stat bonuses. Both cases require pre-emptive crafting of an available supply.
The fleet can collectively maintain a minimum supply in the bank."

USER 2026-10-09, "From the chosen loadouts": for every consumable type some
character's chosen loadout uses, the minimum BANKED quantity is Σ over those
characters of (units used per fight × `REFILL_HORIZON_FIGHTS`); a type nobody's
loadout uses has no minimum. "Need ledger + API order": each character
publishes its need (`ConsumableNeed`), and the bank is assigned in the
account's `GET /my/characters` order.

* NEED — the chosen loadout against the fight ahead (`ctx.loadout`,
  `best_loadout.fight_ahead_loadout`; no fight ahead: no need): the potions one
  fight drinks and the food its recovery eats, each × `REFILL_HORIZON_FIGHTS`.
* STOCK — the account BANK only: the floor is a banked minimum, and units in a
  bag or a utility slot are already that character's to use.
* SHORTFALL — per type this character needs, its share
  (`consumable_floor_core.share`) of the fleet's shortfall, when positive. The
  demand board sums the characters' rows, and the shares sum exactly to
  `max(0, Σ needs − bank)` (`Formal.ConsumableFloor.fleetShares_sum`).
"""

from collections.abc import Mapping, Sequence

from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout
from artifactsmmo_cli.ai.consumable_floor_core import REFILL_HORIZON_FIGHTS, share
from artifactsmmo_cli.ai.world_state import WorldState


def consumable_need(loadout: ChosenLoadout | None) -> dict[str, int]:
    """This character's need per consumable: its chosen loadout's use per fight
    × `REFILL_HORIZON_FIGHTS` (see the module doc)."""
    if loadout is None:
        return {}
    need: dict[str, int] = {}
    for code, units in (*loadout.potions, *loadout.food):
        need[code] = need.get(code, 0) + units * REFILL_HORIZON_FIGHTS
    return need


def supply_shortfall(state: WorldState, order: Sequence[str], me: str, need: Mapping[str, int],
                     siblings: Mapping[str, Mapping[str, int]]) -> tuple[tuple[str, int], ...]:
    """(consumable, this character's share) for each type it needs whose share
    of the fleet's shortfall is positive, against the banked stock only."""
    bank = state.bank_items or {}
    fleet = {**siblings, me: need}
    out: list[tuple[str, int]] = []
    for code in need:
        per_char = {name: needs.get(code, 0) for name, needs in fleet.items()}
        owed = share(order, per_char, me, bank.get(code, 0))
        if owed > 0:
            out.append((code, owed))
    return tuple(out)
