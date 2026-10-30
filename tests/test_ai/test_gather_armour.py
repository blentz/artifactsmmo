"""The gather re-arm wears the owned armour its prospecting pays for (ruling
T14f-3): the gathers a piece saves over the gather's quantity, at one
gather's cost, against the cost of the equip it adds, in planner cost units
(ruling T14f-unit)."""

from fractions import Fraction

import attrs
from artifactsmmo_api_client.models.character_schema import CharacterSchema

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GATHER_SECONDS, GatherAction
from artifactsmmo_cli.ai.craft_plan_gen import _with_rearm
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gather_armour import ARMOUR_SLOTS, gather_armour
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from tests.test_ai.fixtures import make_state


def _gd(rate: int) -> GameData:
    """`pearl` drops 1 in `rate` off `spot`; the bag may hold a +100
    prospecting `robe`; the body wears a combat `plate`."""
    gd = GameData()
    gd._item_stats = {
        "robe": ItemStats(code="robe", level=1, type_="body_armor", prospecting=100),
        "plate": ItemStats(code="plate", level=1, type_="body_armor", resistance={"fire": 20},
                           hp_bonus=50),
        "pearl": ItemStats(code="pearl", level=1, type_="resource"),
    }
    gd.recipes_catalog.resource_drops_full = {"spot": [("pearl", rate, 1, 1)]}
    gd._resource_drops = {"spot": "pearl"}
    gd._resource_skill = {"spot": ("fishing", 1)}
    gd._resource_locations = {"spot": [(1, 0)]}
    gd._monster_locations = {"rat": [(2, 0)]}
    gd._monster_level = {"rat": 1}
    return gd


def _gather(k: Fraction, quantity: int) -> GatherAction:
    return GatherAction(resource_code="spot", quantity=quantity, locations=frozenset({(1, 0)}),
                        drop_item_override="pearl", learned_drops=LearnedDrops((), (), k))


def _state():
    return make_state(skills={**make_state().skills, "fishing": 5}, inventory={"robe": 1},
                      equipment={**make_state().equipment, "body_armor_slot": "plate"})


def _robe_saving(gather: GatherAction, gd: GameData) -> Fraction:
    state = _state()
    worn = EquipAction(code="robe", slot="body_armor_slot").apply(state, gd)
    return (gather.gathers(state, gd) - gather.gathers(worn, gd)) * GATHER_SECONDS


def test_the_armour_slots_leave_out_the_tool_the_artifacts_and_the_potions() -> None:
    assert "body_armor_slot" in ARMOUR_SLOTS
    assert not {"weapon_slot", "artifact1_slot", "utility1_slot"} & set(ARMOUR_SLOTS)


def test_prospecting_armour_is_worn_when_its_saved_cost_exceeds_its_swap() -> None:
    """1 in 2 at k = 1/100: the +100 robe makes the pearl sure, so ten pearls
    take 10 gathers, not 20: 60 saved against a 1.0 equip. The combat plate
    comes off for it."""
    gd = _gd(rate=2)
    gather = _gather(Fraction(1, 100), quantity=10)
    assert _robe_saving(gather, gd) == 60
    assert gather_armour(gather, _state(), gd) == [EquipAction(code="robe", slot="body_armor_slot")]
    plan = _with_rearm([gather], _state(), gd)
    assert plan == [EquipAction(code="robe", slot="body_armor_slot"), gather]


def test_prospecting_armour_is_not_worn_when_its_saving_is_below_the_swap() -> None:
    """One pearl at k = 1/10000: the robe saves 2 - 2/1.01 gathers, about
    0.12, under the equip's 1.0."""
    gd = _gd(rate=2)
    gather = _gather(Fraction(1, 10000), quantity=1)
    saving = _robe_saving(gather, gd)
    assert 0 < saving < 1
    assert gather_armour(gather, _state(), gd) == []
    assert _with_rearm([gather], _state(), gd) == [gather]


def test_prospecting_armour_is_not_worn_for_a_sure_primary_drop() -> None:
    gd = _gd(rate=1)
    gather = _gather(Fraction(1, 100), quantity=10)
    assert _robe_saving(gather, gd) == 0
    assert gather_armour(gather, _state(), gd) == []


def test_the_swap_back_is_not_charged_twice_before_a_fight() -> None:
    """k = 1/700 and one pearl: the robe saves 2 - 2/(8/7) = 1/4 gather, 1.5:
    above the equip (1.0) but below the equip plus a swap back (2.0). The
    fight's own re-arm pays the swap back, so the robe is still worn."""
    gd = _gd(rate=2)
    gather = _gather(Fraction(1, 700), quantity=1)
    assert _robe_saving(gather, gd) == Fraction(3, 2)
    fight = FightAction(monster_code="rat", locations=frozenset({(2, 0)}),
                        learned_drops=LearnedDrops.empty())
    plan = _with_rearm([gather, fight], _state(), gd)
    assert plan == [EquipAction(code="robe", slot="body_armor_slot"), gather, fight]


def test_of_two_paying_pieces_the_larger_saving_is_worn() -> None:
    """`apron` (+40) is visited first and pays too; the robe saves more."""
    gd = _gd(rate=2)
    gd._item_stats["apron"] = ItemStats(code="apron", level=1, type_="body_armor", prospecting=40)
    gather = _gather(Fraction(1, 100), quantity=10)
    state = make_state(skills={**make_state().skills, "fishing": 5},
                       inventory={"robe": 1, "apron": 1})
    assert gather_armour(gather, state, gd) == [EquipAction(code="robe", slot="body_armor_slot")]


def test_an_equal_saving_goes_to_the_higher_level_piece() -> None:
    """`robe` (level 1) is visited first; `tunic` (level 3) saves the same."""
    gd = _gd(rate=2)
    gd._item_stats["tunic"] = ItemStats(code="tunic", level=3, type_="body_armor", prospecting=100)
    gather = _gather(Fraction(1, 100), quantity=10)
    state = make_state(skills={**make_state().skills, "fishing": 5},
                       inventory={"robe": 1, "tunic": 1})
    assert gather_armour(gather, state, gd) == [EquipAction(code="tunic", slot="body_armor_slot")]


def test_a_full_tie_goes_to_the_catalogue_s_first_piece_not_the_first_by_name() -> None:
    """Final review minor 1: `zz_robe` and `aa_robe` save the same and share
    a level. The tie keeps the first in the API item catalogue's order
    (`zz_robe`, listed first), not the first by name."""
    gd = _gd(rate=2)
    gd._item_stats = {
        "zz_robe": ItemStats(code="zz_robe", level=1, type_="body_armor", prospecting=100),
        "aa_robe": ItemStats(code="aa_robe", level=1, type_="body_armor", prospecting=100),
        **gd._item_stats}
    gather = _gather(Fraction(1, 100), quantity=10)
    state = make_state(skills={**make_state().skills, "fishing": 5},
                       inventory={"aa_robe": 1, "zz_robe": 1})
    assert gather_armour(gather, state, gd) == [
        EquipAction(code="zz_robe", slot="body_armor_slot")]


def test_the_armour_slots_are_visited_in_the_api_slot_order() -> None:
    """Ruling FR-slots: the slots come in `CharacterSchema`'s `*_slot` order,
    as `ITEM_TYPE_TO_SLOTS` derives it, not by name: the helmet before the
    body armour, the rune before the shield."""
    schema = [f.name for f in attrs.fields(CharacterSchema) if f.name.endswith("_slot")]
    assert list(ARMOUR_SLOTS) == [slot for slot in schema if slot in ARMOUR_SLOTS]
    assert ARMOUR_SLOTS.index("helmet_slot") < ARMOUR_SLOTS.index("body_armor_slot")


def test_a_later_slot_is_judged_on_the_armour_already_picked() -> None:
    """The helmet slot comes first (ruling FR-slots): the +100 hood makes the
    pearl sure, so the robe (body armour) then saves nothing and is left in
    the bag."""
    gd = _gd(rate=2)
    gd._item_stats["hood"] = ItemStats(code="hood", level=1, type_="helmet", prospecting=100)
    gather = _gather(Fraction(1, 100), quantity=10)
    state = make_state(skills={**make_state().skills, "fishing": 5},
                       inventory={"robe": 1, "hood": 1})
    assert ARMOUR_SLOTS.index("helmet_slot") < ARMOUR_SLOTS.index("body_armor_slot")
    assert gather_armour(gather, state, gd) == [EquipAction(code="hood", slot="helmet_slot")]


def test_the_armour_saving_counts_the_tool_the_re_arm_puts_on() -> None:
    """The bagged +100 net (the fishing tool) makes the pearl sure at the
    gather loadout's prospecting, so the robe saves nothing: the plan wears
    the tool alone."""
    gd = _gd(rate=2)
    gd._item_stats["net"] = ItemStats(code="net", level=1, type_="weapon",
                                      skill_effects={"fishing": -10}, prospecting=100)
    gather = _gather(Fraction(1, 100), quantity=10)
    state = make_state(skills={**make_state().skills, "fishing": 5},
                       inventory={"robe": 1, "net": 1})
    plan = _with_rearm([gather], state, gd)
    assert [type(a).__name__ for a in plan] == ["OptimizeLoadoutAction", "GatherAction"]
