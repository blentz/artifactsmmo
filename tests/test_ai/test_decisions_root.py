"""The ROOT graph (`ai/decisions/root.py`): `resolve_root` from
`WhichPieceIsNext`, `IsThisTargetBlocked` on each `GearTarget` shape, the held
task (`_task_root`), the fleet work and the orphan skill roots.

Built on a real `CharacterObjective` over a small real `GameData`.
`classify_target` emits FOUR shapes: skill-gated, attainable, blocked on a
material, and blocked on ITSELF; `IsThisTargetBlocked` has a test for each.
"""
from dataclasses import replace
from fractions import Fraction

import pytest

from artifactsmmo_cli.ai import gather_demand as _gather_demand
from artifactsmmo_cli.ai.decisions.root import (
    IsThisTargetBlocked,
    RootWalk,
    _orphan_skill_roots,
    resolve_root,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective_context import attach_gear_objective
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.scenario import SCENARIOS, derived_scenario_state, scenario_state
from artifactsmmo_cli.ai.skill_grindable import skill_is_grindable
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.progression.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
    ReachTaskOutcome,
)
from artifactsmmo_cli.ai.progression.objective import CharacterObjective, GearTarget
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT, make_state, served_game_data
from tests.test_ai.test_strategy_driver import _ctx

# The five gear candidates below are chosen so that ONE slot lands in each of
# `classify_target`'s outcomes:
#
#   shield_slot     iron_shield    gearcrafting 10 vs the character's 1 -> SKILL-gated
#   weapon_slot     ash_club       ash_plank <- ash_wood <- ash_tree     -> ATTAINABLE
#   helmet_slot     copper_helmet  copper_bar <- copper_ore <- rocks     -> ATTAINABLE
#   leg_armor_slot  leather_legs   leather has no acquisition source     -> MATERIAL-gated
#   boots_slot      leather_boots  ditto, same material and quantity     -> MATERIAL-gated
#
# The last two deliberately collide on `ObtainItem("leather", 2)`, which is
# what makes the alternatives dedupe observable.
#
# copper_helmet carries its REAL recipe.


def _gd() -> GameData:
    gd = served_game_data()
    gd._item_stats = {
        "iron_shield": ItemStats(code="iron_shield", level=10, type_="shield",
                                 resistance={"earth": 20},
                                 crafting_skill="gearcrafting", crafting_level=10),
        "ash_club": ItemStats(code="ash_club", level=1, type_="weapon",
                              attack={"air": 4},
                              crafting_skill="weaponcrafting", crafting_level=1),
        # THE REAL copper_helmet: gearcrafting@1 from `copper_bar` x6, and
        # copper_bar is mining@1 from copper_ore x10 — all three read off the
        # committed bundle, not invented to make a test pass.
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   resistance={"water": 4},
                                   crafting_skill="gearcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "leather_legs": ItemStats(code="leather_legs", level=1, type_="leg_armor",
                                  resistance={"air": 3},
                                  crafting_skill="gearcrafting", crafting_level=1),
        "leather_boots": ItemStats(code="leather_boots", level=1, type_="boots",
                                   resistance={"fire": 3},
                                   crafting_skill="gearcrafting", crafting_level=1),
        # woodcutting@1, as in the committed bundle: a recipe with no crafting
        # skill has no workshop, so the obtain model has nowhere to craft it.
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource",
                               crafting_skill="woodcutting", crafting_level=1),
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        "leather": ItemStats(code="leather", level=1, type_="resource"),
        "iron_bar": ItemStats(code="iron_bar", level=1, type_="resource"),
    }
    gd._crafting_recipes = {
        "iron_shield": {"iron_bar": 6},
        "ash_club": {"ash_plank": 4},
        "ash_plank": {"ash_wood": 1},
        "copper_helmet": {"copper_bar": 6},
        "copper_bar": {"copper_ore": 10},
        "leather_legs": {"leather": 2},
        "leather_boots": {"leather": 2},
    }
    gd._resource_drops = {"ash_tree": "ash_wood", "copper_rocks": "copper_ore"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1),
                          "copper_rocks": ("mining", 1)}
    # Somewhere to gather and to craft: a skill root's grind rung is obtainable
    # only through routes the executor can serve.
    gd._resource_locations = {"ash_tree": [(1, 0)], "copper_rocks": [(2, 0)]}
    gd._workshop_locations = {"gearcrafting": (0, 1), "weaponcrafting": (0, 2),
                              "mining": (0, 3), "woodcutting": (0, 4)}
    return gd


def _objective(gd: GameData) -> CharacterObjective:
    return CharacterObjective.from_game_data(gd)


def _geared_state():
    """A character already wearing every candidate: no slot is behind."""
    base = make_state(level=15)
    equipment = dict(base.equipment)
    equipment.update(weapon_slot="ash_club", shield_slot="iron_shield",
                     helmet_slot="copper_helmet", leg_armor_slot="leather_legs",
                     boots_slot="leather_boots")
    return make_state(level=15, equipment=equipment)


def _target(**kw) -> GearTarget:
    base = dict(code="iron_shield", attainable=False, blocker=None)
    base.update(kw)
    return GearTarget(**base)


# ---------------------------------------------------------------------------
# IsThisTargetBlocked — one test per arm of the FOUR GearTarget shapes
# ---------------------------------------------------------------------------

def _blocked(target: GearTarget, slot: str = "shield_slot", state=None):
    gd = _gd()
    return IsThisTargetBlocked(slot, target, RootWalk()).resolve(
        state if state is not None else make_state(level=15), gd, _ctx(), None)


def test_a_skill_gated_target_raises_the_skill_by_one():
    """gearcrafting 1 against a level-10 craft: the root is +1, not the
    target level — the graph re-derives every cycle and the increment
    advances on its own."""
    result = _blocked(_target(blocking_skill="gearcrafting",
                              blocking_skill_level=10))
    assert result == ReachSkillLevel(skill="gearcrafting", level=2)


def test_the_skill_gate_is_read_before_the_blocker_field():
    """A skill-gated target also carries `blocker=None`. Testing `blocker is
    None` first would report it as ATTAINABLE and the character would chase a
    craft it cannot perform."""
    result = _blocked(_target(code="iron_shield", blocking_skill="gearcrafting",
                              blocking_skill_level=10, blocker=None))
    assert not isinstance(result, ObtainItem)


def test_an_attainable_target_becomes_an_obtain_item_for_that_slot():
    result = _blocked(_target(code="ash_club", attainable=True, blocker=None),
                      slot="weapon_slot")
    assert result == ObtainItem(code="ash_club", quantity=1, slot="weapon_slot")


def test_a_material_gated_target_routes_to_the_material_at_its_recipe_quantity():
    result = _blocked(_target(code="leather_boots", blocker="leather"),
                      slot="boots_slot")
    assert result == ObtainItem(code="leather", quantity=2)


def test_a_target_that_is_its_own_blocker_routes_to_the_target_itself():
    """`classify_target`'s last arm: no recipe (or none of the recipe is out
    of reach) and the item still is not attainable. There is no material to
    route to."""
    result = _blocked(_target(code="copper_helmet", blocker="copper_helmet"),
                      slot="helmet_slot")
    assert result == ObtainItem(code="copper_helmet", quantity=1,
                                slot="helmet_slot")


def test_a_blocker_that_is_not_in_the_recipe_is_an_error():
    with pytest.raises(ValueError, match="not in its recipe"):
        _blocked(_target(code="leather_boots", blocker="iron_bar"),
                 slot="boots_slot")


def test_a_blocker_on_an_uncraftable_target_is_an_error():
    with pytest.raises(ValueError, match="not in its recipe"):
        _blocked(_target(code="copper_helmet", blocker="leather"),
                 slot="helmet_slot")


# ---------------------------------------------------------------------------
# resolve_root — the whole walk
# ---------------------------------------------------------------------------

def _pieces(*codes: tuple[str, str]) -> GearObjective:
    """A gear objective missing `codes` ((slot, code) pairs), in that order."""
    pieces = tuple(GearPiece(slot, code, 0, Fraction(1), Fraction(1), SourceKind.CRAFT)
                   for slot, code in codes)
    return GearObjective("chicken", {slot: code for slot, code in codes}, Fraction(1), pieces)


_FIVE = _pieces(("shield_slot", "iron_shield"), ("weapon_slot", "ash_club"),
                ("helmet_slot", "copper_helmet"), ("leg_armor_slot", "leather_legs"),
                ("boots_slot", "leather_boots"))
"""The fixture's five candidates as missing `L*` pieces, in the order the
old slot walk ranked them (the skill-gated shield first)."""

_HELD = _pieces()
"""An objective whose `L*` is held: nothing missing."""


def _with(objective: GearObjective | None, **kw):  # type: ignore[no-untyped-def]
    return replace(_ctx(**kw), gear_objective=objective)


def test_resolve_root_walks_the_first_piece_to_its_skill_gate_and_names_the_path():
    gd = _gd()
    resolution = resolve_root(make_state(level=15), gd, _objective(gd), _with(_FIVE), None)
    assert resolution.root == ReachSkillLevel(skill="gearcrafting", level=2)
    assert resolution.trail == ("WhichPieceIsNext", "IsThisTargetBlocked")


def test_the_other_pieces_become_the_alternatives_then_the_task_then_the_orphans():
    """leg_armor and boots are both blocked on two `leather`, so they resolve
    to the SAME `ObtainItem` and appear once.

    ORDERED GROUPS, and the order is the whole contract: every other missing
    piece in the objective's order, then (no trunk: a piece is missing, spec
    2026-10-18 §6.2) the task, then the orphan skill roots
    (`_orphan_skill_roots`). The orphan group admits only a skill the DAG
    DEMANDS (USER 2026-10-08): `ash_tree` and `copper_rocks` gate at
    woodcutting@1 and mining@1, this character already stands at the floor,
    so nothing UNMET is asked for and the group is EMPTY — see
    `tests/test_ai/test_orphan_skill_roots_demand.py` for the group admitting
    a skill when something genuinely demands it."""
    gd = _gd()
    resolution = resolve_root(make_state(level=15), gd, _objective(gd), _with(_FIVE), None)
    assert resolution.alternatives == (
        ObtainItem(code="ash_club", quantity=1, slot="weapon_slot"),
        ObtainItem(code="copper_helmet", quantity=1, slot="helmet_slot"),
        ObtainItem(code="leather", quantity=2),
        # The task objective: the ctx owes a draw (Phase 5-2c-iii-c-2 #3 —
        # the accept is its step).
        ReachTaskOutcome(task_code=None),
    )


def test_the_walk_is_history_free():
    """The head is the objective's first piece on every call: the walk holds
    no history. Rotation away from a stuck head is the intention's job (its
    stall and budget end it, and a spent budget's goal yields one turn in the
    arbiter, Phase 4-2b), not the walk's."""
    gd = _gd()
    state = make_state(level=15)
    heads = {repr(resolve_root(state, gd, _objective(gd), _with(_FIVE), None).root)
             for _ in range(10)}
    assert heads == {repr(ReachSkillLevel(skill="gearcrafting", level=2))}


def test_converting_a_sibling_does_not_pollute_the_trail():
    """The other four pieces are each resolved through `IsThisTargetBlocked`
    to become MetaGoals. Those visits use a throwaway walk, so the trail names
    only the nodes the real walk went through."""
    gd = _gd()
    resolution = resolve_root(make_state(level=15), gd, _objective(gd), _with(_FIVE), None)
    assert resolution.trail.count("IsThisTargetBlocked") == 1


def test_the_chosen_root_is_never_repeated_as_its_own_alternative():
    """A held objective's root is the trunk, `ReachCharLevel(level + 1)`; the
    trunk is offered only while held, and here it IS the root, so it is not
    repeated as its own alternative. The demand gate leaves the orphan group
    empty for the reason the alternatives test gives."""
    gd = _gd()
    resolution = resolve_root(_geared_state(), gd, _objective(gd), _with(_HELD), None)
    assert resolution.root == ReachCharLevel(level=16)
    assert resolution.alternatives == (
        ReachTaskOutcome(task_code=None),  # the owed draw, behind the trunk-root
    )
    assert resolution.trail == ("WhichPieceIsNext",)


def test_a_wall_offers_no_trunk():
    """No gear objective (no achievable loadout pays XP anywhere) is the wall:
    no root, and no trunk on offer, since there is no monster to grind it on.
    The task and orphan roots are still offered."""
    gd = _gd()
    resolution = resolve_root(_geared_state(), gd, _objective(gd), _with(None), None)
    assert resolution.root is None
    assert resolution.alternatives == (ReachTaskOutcome(task_code=None),)


# ---------------------------------------------------------------------------
# The restored standalone skill root — `_orphan_skill_roots`
#
# `ef67c1d6` deleted four standalone `ReachSkillLevel` emitters on the premise
# "skills are pure prerequisites now". These tests state the rule that premise
# is false for, and the catalogue ones answer about the GAME rather than about
# a fixture.
# ---------------------------------------------------------------------------

def test_the_rule_admits_exactly_the_demanded_skills(bundle_game_data: GameData):
    """The rule, end to end, on a real scenario character. `offered` is one
    real item per gathering skill, each chosen off the live bundle's own
    `RequirementGraph.gather_skill` for a gate ABOVE this character's floor:
    `birch_wood` (woodcutting@20), `golden_shrimp` (fishing@10), `nettle_leaf`
    (alchemy@20), and `steel_bar` (mining@20, via its `coal` ingredient).

    Exactly those four are admitted, each at the DEMANDED level, never
    `C+1` — `l1_fresh` stands every skill at the floor, so cooking and the
    three gear-crafting skills each have an open rung and are NOT admitted:
    nothing asks for them (USER 2026-10-08, "Only when demanded").

    `l1_fresh` is the tie case (every skill at the floor), so the order is
    `SKILL_NAMES`."""
    state = derived_scenario_state(SCENARIOS["l1_fresh"], bundle_game_data)
    offered = [ObtainItem(code=code, quantity=1) for code in
              ("birch_wood", "golden_shrimp", "nettle_leaf", "steel_bar")]
    assert _orphan_skill_roots(state, bundle_game_data, offered, TIMED_NO_PROFILE_CONTEXT) == (
        ReachSkillLevel(skill="alchemy", level=20),
        ReachSkillLevel(skill="fishing", level=10),
        ReachSkillLevel(skill="mining", level=20),
        ReachSkillLevel(skill="woodcutting", level=20))
    assert _orphan_skill_roots(state, bundle_game_data, [], TIMED_NO_PROFILE_CONTEXT) == ()


def test_an_orphan_skill_with_no_open_rung_gets_no_root():
    """The rule's SECOND conjunct, and the reason it is not decoration. A root
    the planner cannot serve is the O1 census's `o1_silent_stall` residual —
    the exact failure this seam exists to prevent — so a skill with no open,
    XP-positive rung must produce NOTHING.

    This fixture has TWO orphan skills, each with one rung: woodcutting
    (`ash_tree` -> `ash_wood`) and mining (`copper_rocks` -> `copper_ore`),
    both level 1. Mining joined them when `copper_helmet` took its real recipe
    — copper_bar is mining@1 — and it is an orphan for the same reason
    woodcutting is: no EQUIPPABLE names it as its `crafting_skill`, so no gear
    target can ever reach it. At skill 50 each rung is deep in the server's
    zero-xp band and `LevelSkill.is_applicable` refuses, so topping both out
    empties the tuple.

    Mining leads the grinding case because the order is the gap to the
    character level and mining (1) trails further than woodcutting (2).

    THE THIRD CONJUNCT needs its own demand, separate from conjunct 2's own
    rung: `ash_tree`/`copper_rocks` both gate at level 1, which is already MET
    at the floor, so a root naming either would demand nothing. `silver_rocks`
    (mining@5) and `yew_tree` (woodcutting@5) are added ABOVE both fixture
    levels so `offered` creates real UNMET demand without touching conjunct 1
    (neither is an equippable) or conjunct 2 (the existing level-1 resources
    keep the rung open at skill 1 and 2 — this only raises what is DEMANDED).
    At skill 50 the demand is met too (50 >> 5), so conjunct 2 alone is what
    empties the topped case, exactly as the docstring above says."""
    gd = _gd()
    gd._item_stats["silver_ore"] = ItemStats(code="silver_ore", level=5, type_="resource")
    gd._resource_drops["silver_rocks"] = "silver_ore"
    gd._resource_drops_full["silver_rocks"] = [("silver_ore", 100, 1, 1)]
    gd._resource_skill["silver_rocks"] = ("mining", 5)
    gd._item_stats["yew_wood"] = ItemStats(code="yew_wood", level=5, type_="resource")
    gd._resource_drops["yew_tree"] = "yew_wood"
    gd._resource_drops_full["yew_tree"] = [("yew_wood", 100, 1, 1)]
    gd._resource_skill["yew_tree"] = ("woodcutting", 5)
    offered = [ObtainItem(code="silver_ore", quantity=1),
              ObtainItem(code="yew_wood", quantity=1)]
    grinding = make_state(level=15, skills={"woodcutting": 2})
    assert [r.skill for r in _orphan_skill_roots(
        grinding, gd, offered, TIMED_NO_PROFILE_CONTEXT)] == ["mining", "woodcutting"]
    topped = make_state(level=15, skills={"woodcutting": 50, "mining": 50})
    assert _orphan_skill_roots(topped, gd, offered, TIMED_NO_PROFILE_CONTEXT) == ()
    # DEMANDED BUT NO OPEN RUNG: `gold_ore` asks for mining@20 while mining 16
    # stands past the zero-XP band of every lower rock (copper@1, silver@5,
    # gap >= 11) and below gold. The demand stands; the open-rung conjunct
    # alone is what refuses the root.
    gd._item_stats["gold_ore"] = ItemStats(code="gold_ore", level=20, type_="resource")
    gd._resource_drops["gold_rocks"] = "gold_ore"
    gd._resource_drops_full["gold_rocks"] = [("gold_ore", 100, 1, 1)]
    gd._resource_skill["gold_rocks"] = ("mining", 20)
    walled = make_state(level=30, skills={"woodcutting": 50, "mining": 16})
    gold = [ObtainItem(code="gold_ore", quantity=1)]
    assert _gather_demand.gather_demand(gold, walled, gd, TIMED_NO_PROFILE_CONTEXT) == {"mining": 20}
    assert not skill_is_grindable("mining", 17, walled, gd)
    assert _orphan_skill_roots(walled, gd, gold, TIMED_NO_PROFILE_CONTEXT) == ()


def test_the_orphan_order_is_the_gap_to_the_character_level(
        bundle_game_data: GameData):
    """ONE INTEGER decides, and it is `skill level - character level` (the
    skill trailing furthest goes first). Two states over the same catalogue,
    differing only in WHICH demanded skill trails further, must swap the head —
    a fixed vocabulary order alone could not do that. alchemy and woodcutting
    are parked at their demanded level (20) so the contest is fishing against
    mining and nothing else."""
    base = derived_scenario_state(SCENARIOS["l1_fresh"], bundle_game_data)
    offered = [ObtainItem(code=code, quantity=1) for code in
              ("birch_wood", "golden_shrimp", "nettle_leaf", "steel_bar")]
    parked = {"alchemy": 20, "woodcutting": 20}
    fish_ahead = replace(base, level=20,
                         skills={**base.skills, **parked, "fishing": 8, "mining": 5})
    assert [r.skill for r in _orphan_skill_roots(
        fish_ahead, bundle_game_data, offered, TIMED_NO_PROFILE_CONTEXT)] == ["mining", "fishing"]
    mine_ahead = replace(base, level=20,
                         skills={**base.skills, **parked, "fishing": 5, "mining": 15})
    assert [r.skill for r in _orphan_skill_roots(
        mine_ahead, bundle_game_data, offered, TIMED_NO_PROFILE_CONTEXT)] == ["fishing", "mining"]


def test_cooking_climbs_when_a_better_tier_food_is_due(bundle_game_data: GameData):
    """USER 2026-10-08: "Cooking rises when a better tier food is due, not
    before." The fisher (cooking 21) is offered no cooking climb until the
    fleet floor is short of `cooked_bass` (cooking 30); then the walk offers
    the climb to the level the food asks for. `resolve_root` could not yield
    a cooking root at all before the orphan seam: no cooking recipe produces
    an equippable."""
    state = derived_scenario_state(SCENARIOS["l24_fisher_cooking_rung"], bundle_game_data)
    objective = CharacterObjective.from_game_data(bundle_game_data)

    def skill_roots(ctx):  # type: ignore[no-untyped-def]
        res = resolve_root(state, bundle_game_data, objective, ctx, None)
        return [g for g in (res.root, *res.alternatives) if isinstance(g, ReachSkillLevel)]

    assert not any(g.skill == "cooking" for g in skill_roots(_ctx()))
    due = replace(_ctx(), supply_shortfall=(("cooked_bass", 10),))
    assert ReachSkillLevel(skill="cooking", level=30) in skill_roots(due)


def test_the_orphan_roots_sit_behind_the_trunk(bundle_game_data: GameData):
    """The ORDER is the safety property, and it was measured rather than
    guessed. `objective_step_goal`'s `ReachCharLevel` arm runs
    `_marginal_provision_goal` FIRST, so the trunk slot is also how the
    objective's own provisioning gets planned; an orphan skill climb placed
    ahead of it displaced `GatherMaterials(mithril_bar)` at
    `l48_band_adequate` — the gear that breaks the L38-48 wall. Behind it, an
    orphan root is reached exactly when nothing else can be served. The trunk
    is offered only while `L*` is held, so the objective here is held."""
    state = derived_scenario_state(SCENARIOS["l1_fresh"], bundle_game_data)
    # A short tier food demands cooking and fishing, so the group is not empty.
    due = replace(_with(_HELD), supply_shortfall=(("cooked_shrimp", 10),))
    resolution = resolve_root(state, bundle_game_data,
                              CharacterObjective.from_game_data(bundle_game_data),
                              due, None)
    # Held: the trunk is the root itself, ahead of every alternative.
    alts = (resolution.root, *resolution.alternatives)
    trunk = next(i for i, alt in enumerate(alts)
                 if isinstance(alt, ReachCharLevel))
    skills = [i for i, alt in enumerate(alts) if isinstance(alt, ReachSkillLevel)]
    assert skills, alts
    assert min(skills) > trunk


# --- the blocked target: what the walk drops, and who needs it ---------------

def test_a_skill_gated_pick_records_the_target_it_could_not_build(
        bundle_game_data) -> None:
    """The walk answers a skill-gated slot with a CLIMB, and the target itself
    is dropped — which is the one item a sibling holding that skill could have
    made.

    Measured on the live fleet before this field existed: a blocked character
    publishes no demand at all, `SupplyBank` has executed 0 times in 105,159
    cycles, and `supply_claims` is empty. Recorded by the ONE node that reads
    the gate — a re-derivation in the player would be a second classifier."""
    gd = bundle_game_data
    state = scenario_state(SCENARIOS["l12_deep_chain_grind"], gd)
    ctx = attach_gear_objective(state, gd, TIMED_NO_PROFILE_CONTEXT, None)
    assert ctx.gear_objective is not None
    assert ctx.gear_objective.missing[0].code == "iron_sword"
    resolution = resolve_root(state, gd, CharacterObjective.from_game_data(gd), ctx, None)
    # The objective's first piece, `iron_sword`, needs weaponcrafting 10; the
    # character holds 5, so the walk climbs one level and names the sword.
    assert resolution.root == ReachSkillLevel(skill="weaponcrafting", level=6)
    assert resolution.blocked_target == "iron_sword"


def test_an_unblocked_walk_records_no_blocked_target(bundle_game_data) -> None:
    """`blocked_target` names a SKILL GATE and nothing else: a walk that ends in
    an `ObtainItem` leaves it None, so the player publishes exactly what it did
    before."""
    gd = bundle_game_data
    state = scenario_state(SCENARIOS["l1_fresh"], gd)
    resolution = resolve_root(state, gd, CharacterObjective.from_game_data(gd),
                              attach_gear_objective(state, gd, TIMED_NO_PROFILE_CONTEXT, None),
                              None)
    assert resolution.root == ObtainItem(code="copper_dagger", quantity=1, slot="weapon_slot")
    assert resolution.blocked_target is None
