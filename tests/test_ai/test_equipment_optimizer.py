"""Tests for the equipment optimizer + OptimizeLoadoutAction."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.constants import ERROR_CODE_ALREADY_EQUIPPED
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_gather_loadout, pick_loadout
from artifactsmmo_cli.ai.equipment.scoring import (
    armor_score,
    gather_score,
    weapon_score,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd_with_combat_items() -> GameData:
    gd = GameData()
    gd._item_stats = {
        # wooden_stick is a real combat weapon (subtype="")
        "wooden_stick": ItemStats(
            code="wooden_stick", level=1, type_="weapon",
            attack={"earth": 4},
        ),
        # fishing_net is a GATHER TOOL (subtype="tool") — real game data
        "fishing_net": ItemStats(
            code="fishing_net", level=1, type_="weapon", subtype="tool",
            attack={"water": 5}, skill_effects={"fishing": -10},
        ),
        # copper_axe is a GATHER TOOL (woodcutting)
        "copper_axe": ItemStats(
            code="copper_axe", level=1, type_="weapon", subtype="tool",
            attack={"earth": 5}, skill_effects={"woodcutting": -10},
        ),
        "leather_armor": ItemStats(
            code="leather_armor", level=1, type_="body_armor",
            resistance={"earth": 10},
        ),
        "water_robe": ItemStats(
            code="water_robe", level=1, type_="body_armor",
            resistance={"water": 20},
        ),
    }
    gd._monster_level = {"yellow_slime": 2, "blue_slime": 6}
    gd._monster_attack = {
        "yellow_slime": {"earth": 8, "fire": 0, "water": 0, "air": 0},
        "blue_slime":   {"earth": 0, "fire": 0, "water": 10, "air": 0},
    }
    gd._monster_resistance = {
        "yellow_slime": {"earth": 25, "fire": 0, "water": 0, "air": 0},
        "blue_slime":   {"earth": 0, "fire": 0, "water": 25, "air": 0},
    }
    return gd


class TestWeaponScore:
    def test_unresisted_water_beats_resisted_earth(self):
        gd = _gd_with_combat_items()
        slime_res = gd.monster_resistance("yellow_slime")
        # fishing_net water=5 vs slime res_water=0 → 5
        # wooden_stick earth=4 vs slime res_earth=25 → 3
        assert weapon_score(gd._item_stats["fishing_net"], slime_res) > \
               weapon_score(gd._item_stats["wooden_stick"], slime_res)

    def test_no_attack_zero_raw_plus_nontool_bonus(self):
        """Augmented score = 2*raw + nonToolBonus (Formal/PurposeRouting.lean).
        A zero-attack non-tool weapon still scores 1 from the tiebreaker."""
        gd = _gd_with_combat_items()
        bare = ItemStats(code="empty", level=1, type_="weapon")  # subtype="" → non-tool
        assert weapon_score(bare, gd.monster_resistance("yellow_slime")) == 1

    def test_no_attack_zero_raw_zero_for_tool(self):
        """A zero-attack TOOL scores exactly 0 — no bonus."""
        gd = _gd_with_combat_items()
        bare_tool = ItemStats(code="empty_tool", level=1, type_="weapon", subtype="tool")
        assert weapon_score(bare_tool, gd.monster_resistance("yellow_slime")) == 0

    def test_nontool_tiebreaker_over_tool_on_raw_tie(self):
        """When raw WScores tie, the non-tool weapon strictly outranks the
        tool. Formal closure of the 2026-06-06 fishing_net/wooden_stick
        case at the score level."""
        _gd_with_combat_items()
        # Construct a zero-resistance target so both score 5*100 raw.
        zero_res = {"earth": 0, "fire": 0, "water": 0, "air": 0}
        tool_5atk = ItemStats(code="t5", level=1, type_="weapon", subtype="tool",
                              attack={"earth": 5})
        weapon_5atk = ItemStats(code="w5", level=1, type_="weapon",
                                attack={"earth": 5})
        assert weapon_score(weapon_5atk, zero_res) > weapon_score(tool_5atk, zero_res)
        # And the difference is EXACTLY 1 (the nonToolBonus).
        assert weapon_score(weapon_5atk, zero_res) - weapon_score(tool_5atk, zero_res) == 1

    def test_crit_flips_order_against_resisted_element(self):
        """Run-18 live mis-pick 2026-06-12: vs green_slime (res_air 25)
        copper_pickaxe (earth 5, tool, crit 0) out-scored copper_dagger
        (air 6, crit 35) because weapon_score had NO critical_strike term,
        while predict_win models crit as raw × (1 + crit/100 × 0.5) — the
        loadout picker and the win predictor disagreed about the same
        quantity. Exact surrogate: raw × (200 + crit).
        pickaxe 500×200=100,000 < dagger 450×235=105,750."""
        green_slime_res = {"fire": 0, "earth": 0, "water": 0, "air": 25}
        pickaxe = ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                            subtype="tool", attack={"earth": 5},
                            skill_effects={"mining": -10})
        dagger = ItemStats(code="copper_dagger", level=1, type_="weapon",
                           attack={"air": 6}, critical_strike=35)
        assert weapon_score(dagger, green_slime_res) > \
               weapon_score(pickaxe, green_slime_res)

    def test_pick_loadout_swaps_tool_for_crit_weapon(self):
        """pick_loadout-level run-18 repro: pickaxe equipped, dagger in
        inventory -> the weapon slot delta must be the dagger."""
        gd = GameData()
        gd._item_stats = {
            "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1,
                                        type_="weapon", subtype="tool",
                                        attack={"earth": 5},
                                        skill_effects={"mining": -10}),
            "copper_dagger": ItemStats(code="copper_dagger", level=1,
                                       type_="weapon", attack={"air": 6},
                                       critical_strike=35),
        }
        gd._monster_attack = {"green_slime": {"fire": 0, "earth": 0,
                                              "water": 0, "air": 12}}
        gd._monster_resistance = {"green_slime": {"fire": 0, "earth": 0,
                                                  "water": 0, "air": 25}}
        state = make_state(
            level=7,
            equipment=_equipment_with("copper_pickaxe"),
            inventory={"copper_dagger": 2},
        )
        result = pick_loadout("green_slime", state, gd)
        assert result["weapon_slot"] == "copper_dagger", result


def _equipment_with(weapon_slot: str | None) -> dict[str, str | None]:
    return {
        "weapon_slot": weapon_slot, "rune_slot": None, "shield_slot": None,
        "helmet_slot": None, "body_armor_slot": None, "leg_armor_slot": None,
        "boots_slot": None, "ring1_slot": None, "ring2_slot": None,
        "amulet_slot": None, "artifact1_slot": None, "artifact2_slot": None,
        "artifact3_slot": None, "utility1_slot": None, "utility2_slot": None,
        "bag_slot": None,
    }


class TestGatherScore:
    """Specs from Formal/PurposeRouting.lean — gather picker = argmin gatherScore."""

    def test_picks_skill_specific_tool_when_owned(self):
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={"copper_axe": 1},
            equipment=_equipment_with(weapon_slot="wooden_stick"),
        )
        loadout = pick_gather_loadout("woodcutting", state, gd)
        assert loadout["weapon_slot"] == "copper_axe"

    def test_keeps_current_when_no_gather_tool_owned(self):
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={},
            equipment=_equipment_with(weapon_slot="wooden_stick"),
        )
        loadout = pick_gather_loadout("fishing", state, gd)
        assert loadout["weapon_slot"] == "wooden_stick"

    def test_argmin_picks_most_negative_skill_effect(self):
        gd = GameData()
        gd._item_stats = {
            "weak_axe": ItemStats(code="weak_axe", level=1, type_="weapon",
                                  subtype="tool", attack={"earth": 1},
                                  skill_effects={"woodcutting": -3}),
            "strong_axe": ItemStats(code="strong_axe", level=1, type_="weapon",
                                    subtype="tool", attack={"earth": 1},
                                    skill_effects={"woodcutting": -10}),
        }
        assert gather_score(gd._item_stats["weak_axe"], "woodcutting") == -3
        assert gather_score(gd._item_stats["strong_axe"], "woodcutting") == -10
        state = make_state(
            level=1, inventory={"weak_axe": 1, "strong_axe": 1},
            equipment=_equipment_with(weapon_slot=None),
        )
        loadout = pick_gather_loadout("woodcutting", state, gd)
        assert loadout["weapon_slot"] == "strong_axe"


class TestArmorScore:
    def test_armor_resisting_monster_primary_wins(self):
        gd = _gd_with_combat_items()
        slime_atk = gd.monster_attack("yellow_slime")
        # leather_armor res_earth=10 vs slime atk_earth=8 → 0.8
        # water_robe res_water=20 vs slime atk_water=0 → 0
        assert armor_score(gd._item_stats["leather_armor"], slime_atk) > \
               armor_score(gd._item_stats["water_robe"], slime_atk)


class TestPickLoadout:
    def test_swaps_to_better_weapon_when_available(self):
        gd = _gd_with_combat_items()
        # Char has fishing_net in inventory + wooden_stick equipped. Fighting yellow_slime.
        state = make_state(
            level=1,
            inventory={"fishing_net": 1},
            equipment={"weapon_slot": "wooden_stick"},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        # fishing_net beats wooden_stick vs yellow_slime
        assert loadout["weapon_slot"] == "fishing_net"

    def test_keeps_current_when_no_improvement(self):
        gd = _gd_with_combat_items()
        # Char has only wooden_stick — nothing to swap to
        state = make_state(
            level=1, inventory={},
            equipment={"weapon_slot": "wooden_stick"},
        )
        loadout = pick_loadout("yellow_slime", state, gd)
        assert loadout["weapon_slot"] == "wooden_stick"


class TestOptimizeLoadoutAction:
    def test_applicable_when_swap_improves(self):
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={"fishing_net": 1},
            equipment={"weapon_slot": "wooden_stick"},
        )
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime")
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_when_already_optimal(self):
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={},
            equipment={"weapon_slot": "fishing_net"},
        )
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime")
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_when_no_target_monster(self):
        """Empty target_monster_code is the documented no-target sentinel: no
        swap is computed and the action is inert (line 42-43)."""
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={"copper_dagger": 1},
            equipment={"weapon_slot": "fishing_net"},
        )
        action = OptimizeLoadoutAction(target_monster_code="")
        assert action.is_applicable(state, gd) is False

    def test_apply_updates_equipment_and_inventory(self):
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={"fishing_net": 1},
            equipment={"weapon_slot": "wooden_stick"},
        )
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime")
        new = action.apply(state, gd)
        assert new.equipment["weapon_slot"] == "fishing_net"
        # Old item returns to inventory; new item is consumed
        assert new.inventory.get("wooden_stick", 0) == 1
        assert "fishing_net" not in new.inventory

    def test_cost_scales_with_swap_count(self):
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={"fishing_net": 1},
            equipment={"weapon_slot": "wooden_stick"},
        )
        one_swap = OptimizeLoadoutAction(target_monster_code="yellow_slime").cost(state, gd)
        # Cost is positive when a swap is needed
        assert one_swap > 0

    def test_apply_returns_same_state_when_nothing_to_swap(self):
        gd = _gd_with_combat_items()
        # Already optimal: fishing_net equipped, nothing better in inventory.
        state = make_state(
            level=1, inventory={},
            equipment={"weapon_slot": "fishing_net"},
        )
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime")
        result = action.apply(state, gd)
        assert result is state

    def test_apply_keeps_surplus_of_equipped_item_in_inventory(self):
        gd = _gd_with_combat_items()
        # Two fishing_nets in inventory; equipping one must leave one behind.
        state = make_state(
            level=1, inventory={"fishing_net": 2},
            equipment={"weapon_slot": "wooden_stick"},
        )
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime")
        new = action.apply(state, gd)
        assert new.equipment["weapon_slot"] == "fishing_net"
        assert new.inventory["fishing_net"] == 1
        assert new.inventory.get("wooden_stick", 0) == 1

    def test_execute_unequips_old_then_equips_new(self):
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={"fishing_net": 1},
            equipment={"weapon_slot": "wooden_stick"},
        )
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime", game_data=gd)
        client = MagicMock()
        unequipped = make_state(
            level=1, inventory={"fishing_net": 1, "wooden_stick": 1},
            equipment={"weapon_slot": None},
        )
        equipped = make_state(
            level=1, inventory={"wooden_stick": 1},
            equipment={"weapon_slot": "fishing_net"},
        )

        with patch("artifactsmmo_cli.ai.actions.optimize_loadout.UnequipAction") as MockUn:
            MockUn.return_value.execute.return_value = unequipped
            with patch("artifactsmmo_cli.ai.actions.optimize_loadout.EquipAction") as MockEq:
                MockEq.return_value.execute.return_value = equipped
                result = action.execute(state, client)

        MockUn.assert_called_once_with(slot="weapon_slot")
        MockEq.assert_called_once_with(code="fishing_net", slot="weapon_slot")
        assert result.equipment["weapon_slot"] == "fishing_net"

    def test_execute_skips_unequip_when_slot_empty(self):
        gd = _gd_with_combat_items()
        # Empty weapon slot: only an equip should fire, no unequip.
        state = make_state(
            level=1, inventory={"fishing_net": 1},
            equipment={"weapon_slot": None},
        )
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime", game_data=gd)
        client = MagicMock()
        equipped = make_state(
            level=1, inventory={},
            equipment={"weapon_slot": "fishing_net"},
        )

        with patch("artifactsmmo_cli.ai.actions.optimize_loadout.UnequipAction") as MockUn:
            with patch("artifactsmmo_cli.ai.actions.optimize_loadout.EquipAction") as MockEq:
                MockEq.return_value.execute.return_value = equipped
                result = action.execute(state, client)

        MockUn.assert_not_called()
        MockEq.assert_called_once_with(code="fishing_net", slot="weapon_slot")
        assert result.equipment["weapon_slot"] == "fishing_net"

    def test_execute_unequip_only_swap_skips_equip_pass(self):
        """A swap plan that EMPTIES a slot (new_code None) is fully handled by
        the unequip pass; the equip pass skips it. The swap-plan dict format
        carries `str | None` values, so execute must support the None shape
        even though the current pick_loadout never empties a worn slot."""
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={},
            equipment={"weapon_slot": "wooden_stick"},
        )
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime", game_data=gd)
        client = MagicMock()
        unequipped = make_state(
            level=1, inventory={"wooden_stick": 1},
            equipment={"weapon_slot": None},
        )

        with patch("artifactsmmo_cli.ai.actions.optimize_loadout.pick_loadout",
                   return_value={"weapon_slot": None}):
            with patch("artifactsmmo_cli.ai.actions.optimize_loadout.UnequipAction") as MockUn:
                MockUn.return_value.execute.return_value = unequipped
                with patch("artifactsmmo_cli.ai.actions.optimize_loadout.EquipAction") as MockEq:
                    result = action.execute(state, client)

        MockUn.assert_called_once_with(slot="weapon_slot")
        MockEq.assert_not_called()
        assert result.equipment["weapon_slot"] is None
        assert result.inventory["wooden_stick"] == 1

    def test_execute_records_refusal_when_equip_inapplicable_after_divergence(self):
        """Live-divergence safety: if the post-unequip state no longer admits a
        planned equip (here the unequip response LOST the incoming fishing_net
        from inventory), execute must not burn the API call on a guaranteed
        refusal — it skips the doomed equip and reports the cycle through the
        standard failure channel as ApiActionError(485), which the player maps
        to the recorded outcome "error:already_equipped" and a state refresh."""
        gd = _gd_with_combat_items()
        state = make_state(
            level=1, inventory={"fishing_net": 1},
            equipment={"weapon_slot": "wooden_stick"},
        )
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime", game_data=gd)
        client = MagicMock()
        # Diverged: the unequip returned wooden_stick but fishing_net VANISHED,
        # so the REAL EquipAction.is_applicable gate fails pre-flight.
        diverged = make_state(
            level=1, inventory={"wooden_stick": 1},
            equipment={"weapon_slot": None},
        )

        with patch("artifactsmmo_cli.ai.actions.optimize_loadout.UnequipAction") as MockUn:
            MockUn.return_value.execute.return_value = diverged
            with pytest.raises(ApiActionError) as exc_info:
                action.execute(state, client)

        assert exc_info.value.code == ERROR_CODE_ALREADY_EQUIPPED
        assert "fishing_net->weapon_slot" in exc_info.value.message

    def test_execute_requires_game_data(self):
        state = make_state(level=1)
        action = OptimizeLoadoutAction(target_monster_code="yellow_slime")
        with pytest.raises(RuntimeError):
            action.execute(state, MagicMock())

    def test_repr(self):
        assert repr(OptimizeLoadoutAction(target_monster_code="chicken")) == "OptimizeLoadout(chicken)"


class TestActionTagsIntegration:
    def test_optimize_loadout_has_equip_tag(self):
        assert "equip" in OptimizeLoadoutAction.tags
