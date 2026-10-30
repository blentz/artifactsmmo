"""The gather re-arm's armour pass (ruling T14f-3): which owned armour a gather
should wear for the prospecting it carries.

`pick_loadout(Gather(skill))` picks the tool and keeps every other slot as it
is: its purpose knows the skill, not the resource, the drop or its quantity,
so it cannot price prospecting (Task 14f item 3). The re-arm in front of a
planned gather (`craft_plan_gen._with_rearm`) is the one place that knows
them, so the armour is priced there, in seconds:

* the GAIN of wearing a piece in a slot is the gathers it saves over this
  gather's quantity (`GatherAction.gathers`, read at the gather loadout's
  prospecting, `attempt_prospecting.gather_prospecting`, the one basis) times
  one gather's seconds (`GATHER_SECONDS`);
* the COST is the seconds of the swap it adds: the `EquipAction` that puts it
  on, at that action's own cost. The swap back is not charged: when a fight
  follows, that fight's own re-arm (`OptimizeLoadoutAction`) pays for it.

A piece is worn when its gain exceeds its cost. Combat armour may come off for
it. A sure primary drop gains nothing (its chance is capped at one), and while
the learned slope `k` is 0 no prospecting moves a chance, so the pass picks
nothing live until `k > 0`.

The slots are those the gather loadout does not value: every slot but the tool
(weapon), the artifacts (the picker already scores their prospecting) and the
utility slots (potions, not gear). Slots are visited in a fixed order and each
pick is judged on the state the earlier picks leave."""

from fractions import Fraction

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS, EquipAction
from artifactsmmo_cli.ai.actions.gathering import GATHER_SECONDS, GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.utility_slot import UTILITY_SLOTS
from artifactsmmo_cli.ai.world_state import WorldState

_GATHER_VALUED_SLOTS: frozenset[str] = frozenset(
    {"weapon_slot", "artifact1_slot", "artifact2_slot", "artifact3_slot", *UTILITY_SLOTS})
"""Slots the gather loadout already prices: the tool and the artifacts
(`loadout_picker._benefit`), and the utility slots (potions)."""

ARMOUR_SLOTS: tuple[str, ...] = tuple(sorted(
    {slot for slots in ITEM_TYPE_TO_SLOTS.values() for slot in slots} - _GATHER_VALUED_SLOTS))
"""The slots the armour pass fills, in a fixed order."""


def gather_armour(gather: GatherAction, state: WorldState,
                  game_data: GameData) -> list[EquipAction]:
    """The armour equips worth making before `gather` from `state`: per slot,
    the owned piece whose saved seconds most exceed its equip's cost, when any
    does. The gathers are read at the gather loadout's prospecting, so the
    tool the re-arm puts on is already counted."""
    equips: list[EquipAction] = []
    for slot in ARMOUR_SLOTS:
        best: tuple[Fraction, int, str] | None = None
        bare = gather.gathers(state, game_data)
        for code in sorted(state.inventory):
            equip = EquipAction(code=code, slot=slot)
            if not equip.is_applicable(state, game_data):
                continue
            saved = bare - gather.gathers(equip.apply(state, game_data), game_data)
            net = saved * GATHER_SECONDS - Fraction(equip.cost(state, game_data))
            if net <= 0:
                continue
            stats = game_data.item_stats(code)
            assert stats is not None, f"{code}: EquipAction.is_applicable read its stats"
            # Semantic tie chain: the larger net saving, then the higher item
            # level; the code only orders two pieces that tie on both.
            key = (net, stats.level, code)
            if best is None or key[:2] > best[:2]:
                best = key
        if best is not None:
            chosen = EquipAction(code=best[2], slot=slot)
            equips.append(chosen)
            state = chosen.apply(state, game_data)
    return equips
