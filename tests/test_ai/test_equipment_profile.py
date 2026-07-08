"""Equipment-profile weight presets (spec 2026-07-08). Phase 1: presets +
accessor, pure and unwired."""

from artifactsmmo_cli.ai.tiers.equipment_profile import (
    PROFILE_WEIGHTS,
    ProfileKind,
    profile_weights,
)
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
