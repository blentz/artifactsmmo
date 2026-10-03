"""The root walk lets only a gear target whose step can be served head it
(Phase 3-2): decide()-level tests through the `StrategyEngine.decide` seam.

`step_decline` is the cycle's answer for a root's step (`decisions.root.
StepDecline`). It replaced `step_servable` + `_servable_promotion`, which picked
the head first and promoted past an unservable one afterwards, on
`is_plannable`'s verdict.
"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem, no_decline
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _eng(gd: GameData) -> StrategyEngine:
    """Engine over from_game_data (was imported from test_tiers_strategy's
    `_eng` helper, retired with the flat ranking in Phase 4b Task 2)."""
    return StrategyEngine(CharacterObjective.from_game_data(gd))


def _two_root_gd() -> GameData:
    """Fixture with two craftable items so two roots compete (moved here
    from the retired TestStickyCommitment class at THE FLIP — decide-level
    sticky scoring died with the flat ranking; servability demotion did
    not)."""
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"fire": 6}, crafting_skill="weaponcrafting",
                                   crafting_level=1),
        "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                   resistance={"fire": 4}, crafting_skill="gearcrafting",
                                   crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"copper_bar": 6},
        "wooden_shield": {"ash_wood": 4},
    }
    gd._resource_drops = {"rocks": "copper_bar", "tree": "ash_wood"}
    gd._resource_skill = {"rocks": ("mining", 1), "tree": ("woodcutting", 1)}
    gd._monster_level = {"chicken": 1}
    fill_monster_stat_defaults(gd)
    return gd


class TestDecideStepDecline:
    """decide() never lets a gear target whose step declines head the walk."""

    def test_a_declined_top_target_cannot_head_the_walk(self):
        gd = _two_root_gd()
        eng = _eng(gd)
        state = make_state(level=5)
        top = eng.decide(state, gd).chosen_root
        assert isinstance(top, ObtainItem)

        def decline(root: MetaGoal) -> str | None:
            return "no_route" if root == top else None
        filtered = eng.decide(state, gd, step_decline=decline)
        assert isinstance(filtered.chosen_root, ObtainItem)
        assert filtered.chosen_root != top
        # Named, and still offered: after the served sibling, so it heads the
        # walk again the cycle its blocker clears.
        assert filtered.declined == ((repr(top), "no_route"),)
        assert top in filtered.fallback_roots

    def test_every_target_declined_leaves_the_gear_arm(self):
        """Nothing on the sheet can be served: the walk asks the combat/tier arm,
        as when the sheet wants nothing, and names every gear target it passed."""
        gd = _two_root_gd()
        eng = _eng(gd)
        state = make_state(level=5)
        filtered = eng.decide(
            state, gd,
            step_decline=lambda root: "no_route" if isinstance(root, ObtainItem) else None)
        assert not isinstance(filtered.chosen_root, ObtainItem)
        assert len(filtered.declined) == 2
        assert {reason for _root, reason in filtered.declined} == {"no_route"}

    def test_no_decline_is_the_unfiltered_walk(self):
        gd = _two_root_gd()
        eng = _eng(gd)
        state = make_state(level=5)
        plain = eng.decide(state, gd)
        assert plain.declined == ()
        assert eng.decide(state, gd, step_decline=no_decline).chosen_root == plain.chosen_root
