"""Servable-demotion: decide() demotes roots whose step is not plannable now.

decide()-level tests that a top-scored root with an UNSERVABLE step is demoted
so chosen_root is a root the bot can actually work on (the feather_coat
mismatch fix, trace 2026-06-20). The live path is the progression tree's
`_servable_promotion`; the retired flat-ranking pure core (`keep_servable` in
the deleted `servable_filter.py`) died with the flat ranking in Phase 4b.
"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _eng(gd: GameData) -> StrategyEngine:
    """Engine over from_game_data (was imported from test_tiers_strategy's
    `_eng` helper, retired with the flat ranking in Phase 4b Task 2)."""
    return StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())


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


class TestDecideServableFilter:
    """decide() demotes a top-scored root whose step is unservable."""

    def test_unservable_top_root_is_demoted(self):
        gd = _two_root_gd()
        eng = _eng(gd)
        state = make_state(level=5)
        baseline = eng.decide(state, gd)
        top_repr = repr(baseline.chosen_root)
        # Build a step_servable that marks the natural top root UNSERVABLE and
        # everything else servable.
        def servable(root: MetaGoal, _step: MetaGoal) -> bool:
            return repr(root) != top_repr
        filtered = eng.decide(state, gd, step_servable=servable)
        assert repr(filtered.chosen_root) != top_repr, (
            "top root with unservable step must be demoted")

    def test_all_unservable_keeps_natural_top(self):
        gd = _two_root_gd()
        eng = _eng(gd)
        state = make_state(level=5)
        baseline = eng.decide(state, gd)
        # Nothing servable -> graceful fallback to the natural ranking.
        filtered = eng.decide(state, gd, step_servable=lambda r, s: False)
        assert repr(filtered.chosen_root) == repr(baseline.chosen_root)

    def test_none_predicate_is_unfiltered(self):
        gd = _two_root_gd()
        eng = _eng(gd)
        state = make_state(level=5)
        assert repr(eng.decide(state, gd, step_servable=None).chosen_root) == repr(
            eng.decide(state, gd).chosen_root)
