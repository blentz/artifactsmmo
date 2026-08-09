"""The character's body at a rung the walk has climbed to (S-015)."""

import pytest

from artifactsmmo_cli.ai.learning.rung_state_core import HP_PER_LEVEL, projected_max_hp


class TestProjectedMaxHp:
    def test_the_starting_rung_grants_nothing(self):
        """At the level the state was observed at, no level has been gained yet."""
        assert projected_max_hp(285, 12, 12) == 285

    def test_one_level_grants_one_step(self):
        assert projected_max_hp(285, 12, 13) == 285 + HP_PER_LEVEL

    def test_growth_is_linear_in_levels_gained(self):
        """C3P0's real body carried from 12 to 50: 38 levels of grant."""
        assert projected_max_hp(285, 12, 50) == 285 + HP_PER_LEVEL * 38

    @pytest.mark.parametrize("rung", [11, 5, 1, 0])
    def test_a_rung_below_the_state_grants_nothing(self, rung):
        """The walk never goes backwards, and a rung already behind it does not
        take HP away. Pins that the function is total rather than returning a
        figure below the observed body."""
        assert projected_max_hp(285, 12, rung) == 285

    def test_the_grant_matches_the_published_rule(self):
        """`https://docs.artifactsmmo.com/concepts/stats_and_fights/` — "Each level
        up grants: +5 Max HP". Pinned as a named constant so a change to it is a
        deliberate edit against the published rules, not a silent retune."""
        assert HP_PER_LEVEL == 5
