"""ALCHEMY — the eighth skill, and the one the orphan rule wrongly declined.

The coverage matrix's cells-6-12 report flagged that no cell exercises the
alchemy path, and recorded the reason it was thought not to need one: "alchemy
could be routed (potions are utility equippables)". `decisions/root.
_gear_nameable_skills` said the same thing in its own docstring and
`_orphan_skill_roots` acted on it, refusing alchemy a standalone root because a
gear target could supposedly name it.

IT COULD NOT. Measured on the committed bundle before the fix: a gear target
named alchemy in **0 of the 42 scenarios**, and structurally could never name
it. `objective._gear_candidates_by_type` — the ONLY builder of the gear sheet
`_classify_target` reads `blocking_skill` off — skips `stats.type_ ==
"utility"` outright, because the utility slots are served by
`objective.utility_potion_targets` rather than by the gear sheet. Alchemy's
catalogue is 25 recipes: 20 `utility` (refused by that skip) and 5 `consumable`
(mapped to no slot at all). So the nameability claim was a restatement of
`ITEM_TYPE_TO_SLOTS` that had drifted from the code it claimed to describe, and
alchemy was as orphaned as cooking was before `b39705eb` — with the orphan rule
declining it on the strength of the drift.

The fix is one function: `_gear_nameable_skills` now asks
`_gear_candidates_by_type` instead of restating its rule. The O1 census's routed
count moves **194 -> 236 of 336 cells, 7 of 8 skills -> 8 of 8**; PASS (330),
walled (6) and every residual (0) are unchanged, because routing decides only
which cells the `o1_silent_stall` arm can REACH, never whether a rung is open.

NO 43rd SCENARIO, AND THAT IS THE DESIGN'S OWN RULE. The matrix design's §5.4
"what this deliberately does NOT cover" already answers "a cell per skill (8x)":
"the O1 census already sweeps [scenarios] x 8 cells for rung openness ... adding
skill cells would duplicate it." Cell 12 exists for its D11 x D4 PAIR (a cooking
rung fed by a fishing gather), not because cooking is a skill. Alchemy needs no
pair a scenario does not already carry: with the fix it is the HEAD of the
orphan list in 31 of the 42 committed scenarios, `l15_midband` among them. A
43rd character would exercise nothing the corpus does not already reach — which
is the decorative cell this epic exists to refuse. This module is the witness
instead: it names the branch, shows it reached on a committed scenario, and
flips the dimension.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.decisions.root import _gear_nameable_skills, _orphan_skill_roots
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.meta_goal import ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, WorldState
from artifactsmmo_cli.audit.open_rung_completeness import census_state, routed_skills

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

SKILL = "alchemy"
CELL = "l15_midband"
"""The committed scenario this module witnesses on: level 15, alchemy 6 — the
skill furthest behind the character, so it heads the orphan list."""

RUNG = "small_health_potion"
GEAR_NAMEABLE = frozenset({"gearcrafting", "weaponcrafting", "jewelrycrafting"})
PLAN_BUDGET_SECONDS = 5.0
"""Measured 0.3 s for the one `LevelSkill` plan below."""


@pytest.fixture
def state(bundle_game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[CELL], bundle_game_data)


# --- the finding: no gear target can name alchemy ---------------------------

def test_alchemys_whole_catalogue_is_utility_or_consumable(
        bundle_game_data: GameData) -> None:
    """The catalogue fact the rest of this module stands on, stated over the
    GAME rather than over a fixture: every alchemy recipe is a `utility` potion
    (which the gear sheet skips) or a `consumable` (which maps to no slot).

    The `utility` half is why the old reading looked right — those types DO map
    to `utility1_slot`/`utility2_slot`, both real `EQUIPMENT_SLOTS` — so the
    assertion below records that the naive reading is not merely careless, it
    is defensible right up until you read `_gear_candidates_by_type`."""
    recipes = {code: stats for code, stats
               in bundle_game_data.all_item_stats.items()
               if stats.crafting_skill == SKILL}
    assert len(recipes) == 25
    types = {stats.type_ for stats in recipes.values()}
    assert types == {"utility", "consumable"}
    utility = [c for c, s in recipes.items() if s.type_ == "utility"]
    assert len(utility) == 20
    # The trap: `utility` really does map to two real equipment slots.
    assert [s for s in ITEM_TYPE_TO_SLOTS["utility"] if s in EQUIPMENT_SLOTS] == [
        "utility1_slot", "utility2_slot"]
    # And `consumable` really does map to none.
    assert not ITEM_TYPE_TO_SLOTS.get("consumable")


def test_the_gear_sheet_never_offers_an_alchemy_item(
        bundle_game_data: GameData) -> None:
    """The other half: `_gear_candidates_by_type` is the only builder of the
    items `_classify_target` reads `blocking_skill` off, and it yields no
    alchemy code at any level cap. Asserted through `_gear_nameable_skills`,
    the production answer, so the two cannot be made to disagree."""
    assert _gear_nameable_skills(bundle_game_data) == GEAR_NAMEABLE
    assert SKILL not in _gear_nameable_skills(bundle_game_data)


def test_no_scenario_produces_a_gear_target_that_names_alchemy(
        bundle_game_data: GameData) -> None:
    """The measurement, over the whole corpus: 0 of 42. This is what makes the
    old docstring's "alchemy is therefore NOT an orphan" false rather than
    merely unproven — the claim had a witness set and it was empty.

    Every OTHER skill in `GEAR_NAMEABLE` is asserted to appear somewhere in the
    same sweep, so an empty answer for alchemy cannot be a broken sweep."""
    objective = CharacterObjective.from_game_data(bundle_game_data)
    named: set[str] = set()
    for scenario in SCENARIOS.values():
        state = census_state(scenario, bundle_game_data)
        for target in objective.gear_targets_with_blockers(state, None).values():
            if target.blocking_skill:
                named.add(target.blocking_skill)
    assert SKILL not in named
    assert named and named <= GEAR_NAMEABLE


# --- the branch that now carries alchemy, reached ---------------------------

def test_alchemy_heads_the_orphan_list_for_this_cell(
        bundle_game_data: GameData, state: WorldState) -> None:
    """THE BRANCH: `_orphan_skill_roots` — the restored standalone producer —
    emits `ReachSkillLevel(alchemy, C+1)`, and emits it FIRST.

    First because the group's one ordering integer is `skill level - character
    level` and alchemy at 6 trails a level-15 character further than any other
    skill this scenario carries. That is the same rule cooking, fishing, mining
    and woodcutting are ordered by; alchemy joins the group, it does not get a
    seat beside it."""
    orphans = _orphan_skill_roots(state, bundle_game_data)
    assert orphans[0] == ReachSkillLevel(skill=SKILL,
                                         level=state.skills[SKILL] + 1)
    assert [goal.skill for goal in orphans] == [
        SKILL, "cooking", "fishing", "mining", "woodcutting"]


def test_the_alchemy_rung_is_open_and_is_a_potion(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The rung the root stands on: production's own picker names an alchemy
    recipe at or below the current level, and `LevelSkill(alchemy, C+1)` — the
    orphan rule's second conjunct and the O1 census's verdict predicate — is
    applicable through it."""
    assert skill_grind_target(SKILL, state, bundle_game_data) == RUNG
    stats = bundle_game_data.item_stats(RUNG)
    assert stats is not None
    assert (stats.crafting_skill, stats.type_) == (SKILL, "utility")
    assert stats.crafting_level <= state.skills[SKILL]
    assert LevelSkill(skill=SKILL, target_level=state.skills[SKILL] + 1
                      ).is_applicable(state, bundle_game_data)


def test_the_alchemy_root_plans_a_levelskill(
        bundle_game_data: GameData, state: WorldState) -> None:
    """The root reaches an ACTION, which is what "routable" has to mean:
    `ReachSkillLevel(alchemy, C+1)` -> `objective_step_goal`'s skill arm ->
    a `LevelSkill` plan on the live action factory."""
    root = ReachSkillLevel(skill=SKILL, level=state.skills[SKILL] + 1)
    goal = objective_step_goal(root, state, bundle_game_data,
                               NO_PROFILE_CONTEXT, root=root, history=None)
    assert repr(goal) == f"ReachSkill({SKILL}->{state.skills[SKILL] + 1})"
    player = GamePlayer(character=CELL, history=None)
    player.seed_offline(state, bundle_game_data)
    plan = GOAPPlanner().plan(state, goal, list(player._build_actions()),
                              bundle_game_data, history=None,
                              budget_seconds=PLAN_BUDGET_SECONDS)
    assert plan and repr(plan[0]).startswith(f"LevelSkill({SKILL}->")


# --- flipping the dimension -------------------------------------------------

def test_a_real_alchemy_EQUIPPABLE_would_take_the_root_away(
        bundle_game_data: GameData) -> None:
    """PROOF IT BITES, on the dimension itself.

    The rule is "a skill NO gear target can name deserves a root". Flip that
    exact premise — retype one alchemy recipe from `utility` to `ring`, a type
    the gear sheet does rank, changing nothing else — and alchemy becomes
    genuinely nameable, so the orphan rule must decline it. It does: the root
    disappears and the other four orphans are untouched.

    This is the assertion that fails the day the game ships an alchemy-crafted
    equippable, which is exactly the day alchemy stops being an orphan. It also
    fails if anyone deletes the `stats.type_ == "utility"` skip in
    `_gear_candidates_by_type`, because then the UNFLIPPED catalogue already
    names alchemy — verified by mutation."""
    flipped = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    flipped.all_item_stats[RUNG] = dataclasses.replace(
        flipped.all_item_stats[RUNG], type_="ring")
    assert SKILL in _gear_nameable_skills(flipped)

    before = _orphan_skill_roots(
        scenario_state(SCENARIOS[CELL], bundle_game_data), bundle_game_data)
    after = _orphan_skill_roots(
        scenario_state(SCENARIOS[CELL], flipped), flipped)
    assert [goal.skill for goal in before] == [
        SKILL, "cooking", "fishing", "mining", "woodcutting"]
    assert [goal.skill for goal in after] == [
        "cooking", "fishing", "mining", "woodcutting"]


def test_every_scenario_now_routes_alchemy(bundle_game_data: GameData) -> None:
    """THE FIX AS A NUMBER, and the eighth skill closed.

    `test_fisher_cooking_rung.test_every_scenario_now_routes_cooking` used to
    end `assert "alchemy" not in routed`, on the drifted nameability claim. All
    eight skills are routed now; the O1 census's routed count moves 194 -> 236
    of 336 cells, and 7 of 8 skills -> 8 of 8. `routed` widens the reach of the
    `o1_silent_stall` residual and nothing else, which is why PASS, walled and
    all three residual counts are unchanged by this commit."""
    routed: set[str] = set()
    for scenario in SCENARIOS.values():
        cell = routed_skills(census_state(scenario, bundle_game_data),
                             bundle_game_data)
        assert SKILL in cell, scenario.name
        routed |= cell
    assert routed == GEAR_NAMEABLE | {SKILL, "cooking", "fishing", "mining",
                                      "woodcutting"}
