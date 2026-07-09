"""Equipment-profile weight presets (spec 2026-07-08). Phase 1: presets +
accessor, pure and unwired."""

from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.equipment_profile import (
    PROFILE_WEIGHTS,
    ProfileKind,
    is_utility_objective,
    profile_for,
    profile_weights,
    score_for_profile,
)
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.strategy import root_category
from artifactsmmo_cli.ai.tiers.strategic_value import STRATEGIC_SCALE


class TestPresets:
    def test_combat_zeroes_every_efficiency_stat(self):
        combat, wisdom, prospecting, inventory, haste = PROFILE_WEIGHTS[
            ProfileKind.COMBAT]
        assert combat == STRATEGIC_SCALE          # dominant/floor
        assert (wisdom, prospecting, inventory, haste) == (0, 0, 0, 0)

    def test_utility_keeps_combat_floor_and_lifts_efficiency(self):
        combat, wisdom, prospecting, inventory, haste = PROFILE_WEIGHTS[
            ProfileKind.UTILITY]
        assert combat == STRATEGIC_SCALE          # combat FLOOR preserved
        # every efficiency stat is nonzero and strictly below the combat
        # floor (structural combat dominance in shared slots):
        for w in (wisdom, prospecting, inventory, haste):
            assert 0 < w < STRATEGIC_SCALE

    def test_accessor_returns_the_table_row(self):
        assert profile_weights(ProfileKind.COMBAT) == PROFILE_WEIGHTS[
            ProfileKind.COMBAT]
        assert profile_weights(ProfileKind.UTILITY) == PROFILE_WEIGHTS[
            ProfileKind.UTILITY]

    def test_every_kind_has_a_preset(self):
        assert set(PROFILE_WEIGHTS) == set(ProfileKind)


def _combat_item(raw: int) -> ItemStats:
    """A pure-combat item: the whole combat_raw sits in attack.fire, every
    efficiency stat (wisdom/prospecting/inventory_space/haste) at its 0
    default."""
    return ItemStats(code="weapon", level=1, type_="weapon", attack={"fire": raw})


def _utility_item(prospecting: int) -> ItemStats:
    """A pure-utility item: prospecting only, zero combat content (no
    attack/resistance/hp_restore/hp_bonus/dmg/crit/lifesteal/combat_buff)."""
    return ItemStats(code="artifact", level=1, type_="artifact", prospecting=prospecting)


class TestCombatCalibration:
    def test_combat_profile_ranks_weapon_over_prospecting_artifact(self):
        """THE bug-gone pin: under COMBAT, a real combat item strictly
        outranks a high-prospecting utility item (flat equip_value ranked
        the artifact higher — perfect_pearl over a weapon)."""
        weapon = _combat_item(30)
        artifact = _utility_item(201)
        assert score_for_profile(weapon, ProfileKind.COMBAT) > \
            score_for_profile(artifact, ProfileKind.COMBAT)
        # and equip_value (the OLD ruler) gets it wrong — proving the fix
        # is real, not vacuous:
        assert equip_value(artifact) > equip_value(weapon)

    def test_combat_profile_orders_combat_items_by_combat_raw(self):
        lo, hi = _combat_item(10), _combat_item(25)
        assert score_for_profile(hi, ProfileKind.COMBAT) > \
            score_for_profile(lo, ProfileKind.COMBAT)

    def test_combat_profile_ignores_efficiency_entirely(self):
        bare = _combat_item(10)
        plus_utility = ItemStats(
            code="weapon_plus", level=1, type_="weapon",
            attack={"fire": 10}, prospecting=500,
        )
        assert score_for_profile(bare, ProfileKind.COMBAT) == \
            score_for_profile(plus_utility, ProfileKind.COMBAT)


class TestUtilityCalibration:
    def test_utility_profile_orders_zero_combat_gear_by_efficiency(self):
        """In an efficiency slot (no combat items), UTILITY orders by the
        efficiency stats — the artifact IS pursued."""
        lo, hi = _utility_item(50), _utility_item(200)
        assert score_for_profile(hi, ProfileKind.UTILITY) > \
            score_for_profile(lo, ProfileKind.UTILITY)

    def test_utility_profile_still_floors_combat(self):
        """Even under UTILITY the combat floor dominates a shared slot: a
        combat item outranks a pure-utility item (structural dominance —
        combat_raw * SCALE beats efficiency * small weight)."""
        weapon = _combat_item(1)          # even a tiny combat signal
        artifact = _utility_item(999)
        assert score_for_profile(weapon, ProfileKind.UTILITY) > \
            score_for_profile(artifact, ProfileKind.UTILITY)


_SKILL = ReachSkillLevel(skill="weaponcrafting", level=10)
_XP = ReachCharLevel(level=20)
_GEAR = ObtainItem(code="fire_bow", quantity=1, slot="weapon_slot")


class TestIsUtilityObjective:
    def test_skills_is_utility(self):
        assert is_utility_objective(_SKILL) is True

    def test_char_level_and_gear_are_not_utility(self):
        assert is_utility_objective(_XP) is False
        assert is_utility_objective(_GEAR) is False

    def test_taxonomy_tracks_root_category(self):
        """Drift guard: is_utility_objective must agree with root_category's
        'skills' bucket across every tree root type — if root_category gains
        a category, this catches the profile taxonomy going stale."""
        for root in (_SKILL, _XP, _GEAR):
            assert is_utility_objective(root) == (root_category(root) == "skills")


class TestProfileFor:
    def test_plan_gate_forces_combat_when_inadequate(self):
        # ¬band_adequate ⇒ COMBAT, for EVERY root type (the floor):
        for root in (_SKILL, _XP, _GEAR):
            assert profile_for(root, band_adequate=False) is ProfileKind.COMBAT

    def test_utility_objective_when_adequate_is_utility(self):
        assert profile_for(_SKILL, band_adequate=True) is ProfileKind.UTILITY

    def test_combat_objective_when_adequate_is_combat(self):
        assert profile_for(_XP, band_adequate=True) is ProfileKind.COMBAT
        assert profile_for(_GEAR, band_adequate=True) is ProfileKind.COMBAT
