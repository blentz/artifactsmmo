"""Equip actions between two loadouts (S-020)."""

from artifactsmmo_cli.ai.equipment.equip_actions_core import equip_actions


class TestEquipActions:
    def test_an_unchanged_loadout_costs_nothing(self):
        worn = {"weapon_slot": "wooden_staff", "boots_slot": None}
        assert equip_actions(worn, dict(worn)) == 0

    def test_each_changed_slot_is_one_action(self):
        assert equip_actions(
            {"weapon_slot": "wooden_staff", "boots_slot": None},
            {"weapon_slot": "iron_sword", "boots_slot": "iron_boots"}) == 2

    def test_replacing_an_item_is_ONE_action_not_two(self):
        """The game equips into an occupied slot without a separate unequip, so a
        swap is one action. Counting items moved rather than slots changed would
        double every upgrade."""
        assert equip_actions({"weapon_slot": "wooden_staff"},
                             {"weapon_slot": "iron_sword"}) == 1

    def test_taking_a_piece_off_is_also_an_action(self):
        assert equip_actions({"weapon_slot": "iron_sword"},
                             {"weapon_slot": None}) == 1

    def test_an_absent_slot_and_an_explicit_none_are_the_same_thing(self):
        """`WorldState.equipment` carries every slot including the empty ones, while
        a loadout picked for a purpose may simply omit slots it has no opinion
        about. Treating those two spellings as different would invent one action per
        unmentioned empty slot — on a sixteen-slot character, an entire phantom
        loadout change at the very first rung."""
        assert equip_actions({"weapon_slot": None, "boots_slot": None},
                             {"weapon_slot": None}) == 0
        assert equip_actions({}, {"weapon_slot": None, "ring1_slot": None}) == 0

    def test_an_empty_string_reads_as_empty(self):
        """The API reports an unfilled slot as `""`, and `WorldState` normalises it
        to None — but a caller that passes the raw shape must not be charged for it."""
        assert equip_actions({"weapon_slot": ""}, {"weapon_slot": None}) == 0

    def test_slots_only_the_target_names_still_count(self):
        assert equip_actions({}, {"weapon_slot": "iron_sword"}) == 1
