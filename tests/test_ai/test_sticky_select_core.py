"""Tests for the progress-gated sticky select pure core + root progress value.

These cover the Python image of `Formal/Liveness/StickySelect.lean` (`sticky_choose` /
`next_last`) and the `root_progress_value` signal that gates the release. The Lean side
carries the kernel-proved no-zombie theorems; the differential harness
(`formal/diff/test_sticky_select_diff.py`) binds `sticky_choose` to the oracle.
"""

from fractions import Fraction

from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.root_progress import (
    _EQUIPPED_VALUE,
    root_progress_value,
)
from artifactsmmo_cli.ai.tiers.sticky_select_core import (
    StickyCand,
    next_last,
    sticky_choose,
)
from artifactsmmo_cli.ai.world_state import WorldState


def _state(**kw: object) -> WorldState:
    """Minimal WorldState with the fields root_progress_value reads, overridable."""
    base: dict[str, object] = dict(
        character="t", level=1, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        skills={}, x=0, y=0, inventory={}, inventory_max=100, equipment={},
        cooldown_expires=None, task_code=None, task_type=None, task_progress=0,
        task_total=0, bank_items=None, bank_gold=None, pending_items=None,
        skill_xp={},
    )
    base.update(kw)
    return WorldState(**base)  # type: ignore[arg-type]


class TestStickyChoose:
    GEAR = StickyCand("gear", Fraction(5, 2))      # 2.5
    SKILL = StickyCand("skill", Fraction(51, 25))  # 2.04
    RATIO = Fraction(3, 2)

    def test_empty_list_returns_none(self):
        assert sticky_choose([], "anything", self.RATIO) is None

    def test_no_last_chosen_returns_top(self):
        assert sticky_choose([self.GEAR, self.SKILL], None, self.RATIO) is self.GEAR

    def test_last_chosen_equals_top_returns_top(self):
        assert sticky_choose([self.GEAR, self.SKILL], "gear", self.RATIO) is self.GEAR

    def test_sticky_kept_within_dominance_ratio(self):
        # top 2.5 <= 3/2 * 2.04 = 3.06 -> keep sticky skill.
        assert sticky_choose([self.GEAR, self.SKILL], "skill", self.RATIO) is self.SKILL

    def test_sticky_dropped_when_top_dominates(self):
        # top 2.5 > 3/2 * 1.0 = 1.5 -> top wins.
        weak = StickyCand("skill", Fraction(1))
        assert sticky_choose([self.GEAR, weak], "skill", self.RATIO) is self.GEAR

    def test_sticky_candidate_absent_returns_top(self):
        # last_chosen dropped out of the candidate list this cycle.
        assert sticky_choose([self.GEAR, self.SKILL], "vanished", self.RATIO) is self.GEAR


class TestNextLast:
    def test_none_chosen_is_none(self):
        assert next_last(None, True) is None
        assert next_last(None, False) is None

    def test_progressed_feeds_repr(self):
        assert next_last("gear", True) == "gear"

    def test_not_progressed_releases(self):
        assert next_last("gear", False) is None


class TestRootProgressValue:
    def test_skill_level_tracks_that_skills_xp(self):
        root = ReachSkillLevel(skill="weaponcrafting", level=5)
        st = _state(skill_xp={"weaponcrafting": 75, "mining": 2000})
        assert root_progress_value(root, st, None) == 75  # type: ignore[arg-type]

    def test_skill_level_frozen_when_only_other_skill_grows(self):
        # The zombie: gathering raises mining xp, weaponcrafting stays 75 -> no progress.
        root = ReachSkillLevel(skill="weaponcrafting", level=5)
        before = root_progress_value(root, _state(skill_xp={"weaponcrafting": 75, "mining": 600}), None)  # type: ignore[arg-type]
        after = root_progress_value(root, _state(skill_xp={"weaponcrafting": 75, "mining": 760}), None)  # type: ignore[arg-type]
        assert before == after == 75

    def test_char_level_rises_with_level_then_xp(self):
        root = ReachCharLevel(level=8)
        low = root_progress_value(root, _state(level=5, xp=10), None)  # type: ignore[arg-type]
        more_xp = root_progress_value(root, _state(level=5, xp=40), None)  # type: ignore[arg-type]
        leveled = root_progress_value(root, _state(level=6, xp=0), None)  # type: ignore[arg-type]
        assert low < more_xp < leveled

    def test_obtain_equipped_dominates(self):
        root = ObtainItem(code="copper_boots", quantity=1, slot="boots_slot")
        st = _state(equipment={"boots_slot": "copper_boots"})
        assert root_progress_value(root, st, _FakeGameData({})) == _EQUIPPED_VALUE

    def test_obtain_counts_owned_plus_recipe_inputs(self):
        root = ObtainItem(code="copper_boots", quantity=1, slot="boots_slot")
        gd = _FakeGameData({"copper_boots": {"copper_bar": 6}})
        few = root_progress_value(root, _state(inventory={"copper_bar": 2}), gd)
        more = root_progress_value(root, _state(inventory={"copper_bar": 5}), gd)
        assert few == 2 and more == 5

    def test_obtain_no_recipe_counts_owned_only(self):
        root = ObtainItem(code="raw_thing", quantity=1, slot=None)
        gd = _FakeGameData({})
        assert root_progress_value(root, _state(inventory={"raw_thing": 3}), gd) == 3

    def test_unknown_root_type_is_zero(self):
        assert root_progress_value(object(), _state(), None) == 0  # type: ignore[arg-type]


class _FakeGameData:
    """Minimal GameData stand-in exposing only crafting_recipe."""

    def __init__(self, recipes: dict[str, dict[str, int]]) -> None:
        self._recipes = recipes

    def crafting_recipe(self, code: str) -> dict[str, int] | None:
        return self._recipes.get(code)
