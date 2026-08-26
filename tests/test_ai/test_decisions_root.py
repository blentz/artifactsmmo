"""The ROOT graph: one test per branch of every node in `ai/decisions/root.py`.

Nothing in production calls `resolve_root` yet (the flip is a later task of
`PLAN_wave3a_cutover`), so these tests ARE the whole consumer. They are built
on a real `CharacterObjective` over a small real `GameData` rather than on a
stand-in for `gear_targets_with_blockers`: a double returning the three
`GearTarget` shapes by hand would agree with `_classify_target` only for as
long as somebody kept it in step, and this graph's entire job is to read that
producer's output correctly. `_classify_target` emits FOUR shapes, not the
three spec §5.3 tabulates: skill-gated, attainable, blocked on a material, and
blocked on ITSELF. There is a test below for each.

The one doubled collaborator is `tier_progress.is_winnable` — a boolean oracle
over the combat model, monkeypatched so "the ladder is finished" and "a rung is
still open" are both reachable without building a winnable and an unwinnable
monster. That is the idiom `tests/test_ai/test_tier_progress.py` already uses
for the same two branches. Every test that patches it also puts a monster in
the band first: the bare `_gd()` has an EMPTY monster table, `tier_cleared` is
then `all([])`, and the patch would decide nothing — the branch would be
reached by an empty collection instead. Fix-round-1 found exactly that in two
of these tests.
"""
from dataclasses import replace

import pytest

import artifactsmmo_cli.ai.tiers.tier_progress as tier_progress
from artifactsmmo_cli.ai.decisions.root import (
    CanIClearMyTier,
    IsMyGearBehindMyTier,
    IsThereACombatTarget,
    IsThisTargetBlocked,
    RootWalk,
    WhichSlotIsFurthestBehind,
    _gear_nameable_skills,
    _next_rung_above,
    _orphan_skill_roots,
    _tier_gap,
    resolve_root,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.scenario import SCENARIOS
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
    focus_key,
    focus_key_str,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, GearTarget
from artifactsmmo_cli.ai.tiers.progression_tree_core import FOCUS_FLAT, FOCUS_SPAN
from artifactsmmo_cli.ai.tiers.tier_ladder import ladder, normal_band, tier_of_level
from artifactsmmo_cli.audit.open_rung_completeness import census_state
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _ctx

# The five gear candidates below are chosen so that ONE slot lands in each of
# `_classify_target`'s outcomes, and so the tier gaps are not all equal:
#
#   shield_slot     iron_shield    gearcrafting 10 vs the character's 1 -> SKILL-gated
#   weapon_slot     ash_club       ash_plank <- ash_wood <- ash_tree     -> ATTAINABLE
#   helmet_slot     copper_helmet  no recipe, no drop, no vendor         -> its OWN blocker
#   leg_armor_slot  leather_legs   leather has no acquisition source     -> MATERIAL-gated
#   boots_slot      leather_boots  ditto, same material and quantity     -> MATERIAL-gated
#
# The last two deliberately collide on `ObtainItem("leather", 2)`, which is
# what makes the alternatives dedupe observable.
_LADDER_RUNGS = (1, 10)
_HIGH_LADDER_RUNGS = (10, 20)


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "iron_shield": ItemStats(code="iron_shield", level=10, type_="shield",
                                 resistance={"earth": 20},
                                 crafting_skill="gearcrafting", crafting_level=10),
        "ash_club": ItemStats(code="ash_club", level=1, type_="weapon",
                              attack={"air": 4},
                              crafting_skill="weaponcrafting", crafting_level=1),
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   resistance={"water": 4}),
        "leather_legs": ItemStats(code="leather_legs", level=1, type_="leg_armor",
                                  resistance={"air": 3},
                                  crafting_skill="gearcrafting", crafting_level=1),
        "leather_boots": ItemStats(code="leather_boots", level=1, type_="boots",
                                   resistance={"fire": 3},
                                   crafting_skill="gearcrafting", crafting_level=1),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        "leather": ItemStats(code="leather", level=1, type_="resource"),
        "iron_bar": ItemStats(code="iron_bar", level=1, type_="resource"),
    }
    gd._crafting_recipes = {
        "iron_shield": {"iron_bar": 6},
        "ash_club": {"ash_plank": 4},
        "ash_plank": {"ash_wood": 1},
        "leather_legs": {"leather": 2},
        "leather_boots": {"leather": 2},
    }
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


def _gd_two_ways_behind() -> GameData:
    """A second ladder, built for ONE question: what happens when two slots
    are behind by the SAME number of rungs but their targets sit on different
    rungs.

    Over `_gd()` that case cannot arise — every tied gap there is a tie in the
    target rung too (all four rung-1 targets sit in empty slots), so
    `_slot_order`'s middle key is never the one that decides and a mutant of
    it would survive. Here:

        weapon_slot  empty (rung 0)      -> iron_club   (rung 10)  gap 10
        boots_slot   iron_boots (rung 10) -> steel_boots (rung 20)  gap 10

    Same gap, different target rung, and the slots are in the OPPOSITE order
    to the schema tiebreak (weapon is index 0, boots is index 6), so the
    middle key is the only thing that can put boots first.
    """
    gd = GameData()
    gd._item_stats = {
        "iron_club": ItemStats(code="iron_club", level=10, type_="weapon",
                               attack={"air": 10}),
        "iron_boots": ItemStats(code="iron_boots", level=10, type_="boots",
                                resistance={"earth": 10}),
        "steel_boots": ItemStats(code="steel_boots", level=20, type_="boots",
                                 resistance={"earth": 30}),
    }
    return gd


def _objective(gd: GameData) -> CharacterObjective:
    return CharacterObjective(target_char_level=50, target_skill_levels={},
                              target_gear={}, _game_data=gd)


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
# The ladder the gap arithmetic is measured against
# ---------------------------------------------------------------------------

def test_the_fixture_ladder_is_the_two_rungs_the_gap_tests_assume():
    """Anti-vacuity: every gap number below is `rung - rung`, so a fixture
    whose ladder collapsed to one rung would make them all zero and the
    ordering tests would pass on a tie."""
    assert ladder(_gd()) == _LADDER_RUNGS
    assert ladder(_gd_two_ways_behind()) == _HIGH_LADDER_RUNGS


# ---------------------------------------------------------------------------
# IsMyGearBehindMyTier
# ---------------------------------------------------------------------------

def test_gear_behind_the_tier_routes_to_the_slot_walk():
    gd = _gd()
    walk = RootWalk()
    child = IsMyGearBehindMyTier(_objective(gd), walk).resolve(
        make_state(level=15), gd, _ctx(), None)
    assert isinstance(child, WhichSlotIsFurthestBehind)
    assert set(child.targets) == {"weapon_slot", "shield_slot", "helmet_slot",
                                  "leg_armor_slot", "boots_slot"}
    assert walk.trail == ["IsMyGearBehindMyTier"]


def test_no_gear_target_routes_to_the_combat_question():
    gd = _gd()
    child = IsMyGearBehindMyTier(_objective(gd), RootWalk()).resolve(
        _geared_state(), gd, _ctx(), None)
    assert isinstance(child, IsThereACombatTarget)


# ---------------------------------------------------------------------------
# WhichSlotIsFurthestBehind
# ---------------------------------------------------------------------------

def test_the_furthest_behind_slot_is_the_one_that_resolves():
    """shield_slot is 10 rungs behind (empty -> the level-10 rung); every
    other slot is 1. The head is the shield, and the other four are left in
    the walk as siblings."""
    gd = _gd()
    state = make_state(level=15)
    walk = RootWalk()
    node = IsMyGearBehindMyTier(_objective(gd), walk).resolve(state, gd, _ctx(), None)
    assert isinstance(node, WhichSlotIsFurthestBehind)
    child = node.resolve(state, gd, _ctx(), None)
    assert isinstance(child, IsThisTargetBlocked)
    assert child.slot == "shield_slot"
    assert [slot for slot, _ in walk.sibling_targets] == [
        "weapon_slot", "helmet_slot", "leg_armor_slot", "boots_slot"]


def test_equal_gaps_break_on_the_schema_slot_order_not_the_alphabet():
    """weapon/helmet/leg_armor/boots are all 1 rung behind with a rung-1
    target. Alphabetically that is boots, helmet, leg_armor, weapon; the
    schema declares weapon, shield, helmet, leg_armor, boots, and the schema
    order is what the walk uses."""
    gd = _gd()
    state = make_state(level=15)
    walk = RootWalk()
    node = WhichSlotIsFurthestBehind(
        _objective(gd).gear_targets_with_blockers(state, None), walk)
    node.resolve(state, gd, _ctx(), None)
    assert [slot for slot, _ in walk.sibling_targets] == [
        "weapon_slot", "helmet_slot", "leg_armor_slot", "boots_slot"]


def test_equal_gaps_prefer_the_HIGHER_rung_target():
    """The middle key of `_slot_order`. Both slots are 10 rungs behind; boots
    is chasing rung 20 and weapon rung 10, and boots must lead even though the
    schema puts weapon_slot first. Feeding the targets dict straight in is
    deliberate: this node's input IS a `dict[str, GearTarget]` and the claim
    under test is the ORDERING, not how the blocker fields were classified."""
    gd = _gd_two_ways_behind()
    base = make_state(level=25)
    state = make_state(level=25,
                       equipment=dict(base.equipment, boots_slot="iron_boots"))
    targets = {
        "weapon_slot": _target(code="iron_club", attainable=True),
        "boots_slot": _target(code="steel_boots", attainable=True),
    }
    assert _tier_gap("weapon_slot", targets["weapon_slot"], state, gd) == 10
    assert _tier_gap("boots_slot", targets["boots_slot"], state, gd) == 10
    walk = RootWalk()
    child = WhichSlotIsFurthestBehind(targets, walk).resolve(state, gd, _ctx(), None)
    assert isinstance(child, IsThisTargetBlocked)
    assert child.slot == "boots_slot"
    assert [slot for slot, _ in walk.sibling_targets] == ["weapon_slot"]


def test_an_empty_slot_outranks_an_occupied_one_at_the_same_rung():
    """An empty slot counts as rung 0, strictly below the ladder's first rung
    — not `tier_of_level(0)`, which IS the first rung. Wearing a rung-1 item
    and targeting a rung-1 item is a gap of 0; wearing nothing is a gap of 1."""
    gd = _gd()
    target = _target(code="leather_boots", attainable=True)
    empty = make_state(level=15)
    worn = make_state(level=15,
                      equipment=dict(empty.equipment, boots_slot="leather_boots"))
    assert _tier_gap("boots_slot", target, empty, gd) == 1
    assert _tier_gap("boots_slot", target, worn, gd) == 0


def test_a_gear_target_absent_from_game_data_is_an_error_not_a_default_rung():
    gd = _gd()
    with pytest.raises(ValueError, match="no item stats in game data"):
        _tier_gap("boots_slot", _target(code="phantom_boots"),
                  make_state(level=15), gd)


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
    """`_classify_target`'s last arm: no recipe (or none of the recipe is out
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
# IsThereACombatTarget / CanIClearMyTier
# ---------------------------------------------------------------------------

def test_combat_target_root_is_the_next_rung_up_not_the_one_already_reached():
    """THE FLIP's correction to spec §5.3, which named `tier_of_level` — the
    highest rung AT OR BELOW the level, i.e. a root already satisfied. The
    fixture ladder is (1, 10), so at level 5 the answer is rung 10, and 10 is
    strictly above 5: an UNMET root, which is the whole point.

    `is_satisfied` is asserted False directly rather than inferred from the
    level, because that is the property three downstream readers depend on
    (`objective_needs`'s `char_xp`, `actionable_step`'s descent, and the plan
    pane's "why") and the number alone does not state it."""
    gd = _gd()
    state = make_state(level=5)
    result = IsThereACombatTarget(RootWalk()).resolve(
        state, gd, _ctx(combat_monster="chicken"), None)
    assert result == ReachCharLevel(level=10)
    assert isinstance(result, ReachCharLevel) and not result.is_satisfied(state, gd)


def test_combat_target_root_falls_back_to_the_milestone_past_the_last_rung():
    """The ladder-exhausted arm of `_next_rung_above`. The fixture ladder tops
    out at 10, so a level-15 character has no rung above it and the answer is
    `milestone_pure(15) == 20` — still strictly above the level, and the same
    trunk milestone `CanIClearMyTier` falls back on."""
    gd = _gd()
    state = make_state(level=15)
    result = IsThereACombatTarget(RootWalk()).resolve(
        state, gd, _ctx(combat_monster="chicken"), None)
    assert result == ReachCharLevel(level=20)
    assert isinstance(result, ReachCharLevel) and not result.is_satisfied(state, gd)


def test_combat_target_root_at_the_level_cap_is_the_satisfied_capstone():
    """THE END THE FIRST DERIVATION DID NOT CHECK. `_next_rung_above` is
    "strictly above" only while the ladder has a rung left; at the cap it falls
    back to `milestone_pure`, whose L50 fixed point is 50, so a level-50
    character DOES get an already-satisfied root and the three consequences the
    correction was made to remove come back.

    Pinned rather than fixed: there is no level above 50 to name, and
    `CanIClearMyTier` reaches the same fixed point by the same route. It is the
    L50 capstone's own open question (`project_l50_unconditional_descent`), and
    the task-6 report's blanket claim that this arm always names an unreached
    level was false here."""
    gd = _gd()
    state = make_state(level=50)
    result = IsThereACombatTarget(RootWalk()).resolve(
        state, gd, _ctx(combat_monster="chicken"), None)
    assert result == ReachCharLevel(level=50)
    assert isinstance(result, ReachCharLevel) and result.is_satisfied(state, gd)


def test_next_rung_above_refuses_an_empty_ladder_like_its_sibling():
    """`_next_rung_above` RAISES on a catalogue with no equippable items, the
    same as `tier_of_level` — the fail-fast parity F6 asked for. It silently
    returned `milestone_pure` until wave 3a fix-round 1, which would have made
    the two disagree about one data fault while "tier_of_level correctly
    refuses it" was the argument six test fixtures were changed on."""
    with pytest.raises(ValueError, match="no equippable items in game data"):
        _next_rung_above(GameData(), 5)
    with pytest.raises(ValueError, match="no equippable items in game data"):
        tier_of_level(GameData(), 5)


def test_no_combat_target_asks_whether_the_tier_is_clear():
    gd = _gd()
    child = IsThereACombatTarget(RootWalk()).resolve(
        make_state(level=15), gd, _ctx(combat_monster=None), None)
    assert isinstance(child, CanIClearMyTier)


def test_a_finished_ladder_resolves_to_the_trunk_milestone(monkeypatch):
    """The chicken is REQUIRED, not decoration: on the bare `_gd()` the
    monster table is empty, `normal_band(gd, 1)` is `()` and `tier_cleared` is
    `all([])`, so `next_uncleared_tier` already returns None and the patch
    below decides nothing. With a monster in the band the patch is what flips
    the branch. Fix-round-1."""
    gd = _gd()
    gd._monster_level = {"chicken": 1}
    gd._monster_type = {"chicken": "normal"}
    assert normal_band(gd, 1) == ("chicken",)
    monkeypatch.setattr(tier_progress, "is_winnable", lambda s, g, c, h: True)
    result = CanIClearMyTier(RootWalk()).resolve(
        make_state(level=15), gd, _ctx(), None)
    assert result == ReachCharLevel(level=20)


def test_an_open_rung_with_nothing_to_do_is_an_honest_wall(monkeypatch):
    """Gear wants nothing, no monster in the band is winnable, and a rung is
    still open. There is no root — reported as None, not dressed up."""
    gd = _gd()
    gd._monster_level = {"chicken": 1}
    gd._monster_type = {"chicken": "normal"}
    monkeypatch.setattr(tier_progress, "is_winnable", lambda s, g, c, h: False)
    assert CanIClearMyTier(RootWalk()).resolve(
        make_state(level=15), gd, _ctx(), None) is None


# ---------------------------------------------------------------------------
# resolve_root — the whole walk
# ---------------------------------------------------------------------------

def test_resolve_root_walks_gear_to_the_skill_gate_and_names_the_path():
    gd = _gd()
    resolution = resolve_root(make_state(level=15), gd, _objective(gd), _ctx(), None)
    assert resolution.root == ReachSkillLevel(skill="gearcrafting", level=2)
    assert resolution.trail == ("IsMyGearBehindMyTier", "WhichSlotIsFurthestBehind",
                                "IsThisTargetBlocked")


def test_the_siblings_become_the_alternatives_then_the_trunk_then_the_orphans():
    """leg_armor and boots are both blocked on two `leather`, so they resolve
    to the SAME `ObtainItem` and appear once.

    THREE ORDERED GROUPS, and the order is the whole contract: every gear
    sibling, then the trunk, then the orphan skill roots
    (`_orphan_skill_roots`). This fixture's catalogue crafts `ash_plank` from
    woodcutting and nothing woodcutting makes is equippable, so woodcutting is
    an orphan here — the restored seam is exercised by the unit fixture and not
    only by the scenario set."""
    gd = _gd()
    resolution = resolve_root(make_state(level=15), gd, _objective(gd), _ctx(), None)
    assert resolution.alternatives == (
        ObtainItem(code="ash_club", quantity=1, slot="weapon_slot"),
        ObtainItem(code="copper_helmet", quantity=1, slot="helmet_slot"),
        ObtainItem(code="leather", quantity=2),
        ReachCharLevel(level=20),
        ReachSkillLevel(skill="woodcutting", level=3),
    )


def test_the_slot_walk_does_not_rotate_while_every_target_is_fresh():
    """The unaged fast path: with an empty ledger the head is `_slot_order`'s
    argmax on every call, bit-identical to the history-free walk. Every
    ledger-free caller — the whole offline scenario set, `NO_PROFILE_CONTEXT` —
    depends on this."""
    gd = _gd()
    state = make_state(level=15)
    heads = {repr(resolve_root(state, gd, _objective(gd), _ctx(), None).root)
             for _ in range(10)}
    assert heads == {repr(ReachSkillLevel(skill="gearcrafting", level=2))}


def test_an_aged_slot_hands_the_decision_to_an_alternative():
    """THE ANTI-STARVATION FIX AT THE NODE. Age the winning slot past the flat
    farm window and the d'Hondt interleave must hand the head to a different
    slot — and say so, via `aged`, which is what gates the player's seat bump.

    Without this the run_group for `ROOT_DECISION_MUTATIONS` could not reach
    the claim at all: it binds only this file, and the end-to-end rotation
    proof lives in `test_ring2_starvation_repro.py` (the run_group-binding trap
    `test_progression_tree.py` already documents)."""
    gd = _gd()
    state = make_state(level=15)
    fresh = resolve_root(state, gd, _objective(gd), _ctx(), None)
    assert fresh.aged is False
    # The stuck key is `focus_key(fresh.root)` — the RESOLVED root, which is
    # what `GamePlayer._charge_focus` charges and therefore what the walk must
    # read. Derived, not hand-written: this fixture's head is a skill-gated
    # slot, so the key is `("<skill>", "gearcrafting")` and NOT
    # `("shield_slot", "iron_shield")`. A hand-written sheet key here would be
    # the fix-round-2 defect reproduced inside its own regression test.
    stuck_key = focus_key(fresh.root)
    assert stuck_key is not None
    aged_ctx = replace(_ctx(), gear_focus={stuck_key: FOCUS_FLAT + FOCUS_SPAN},
                       interleave_seats={focus_key_str(stuck_key): 40})
    rotated = resolve_root(state, gd, _objective(gd), aged_ctx, None)
    assert rotated.aged is True
    assert rotated.root != fresh.root


def test_converting_a_sibling_does_not_pollute_the_trail():
    """The four siblings are each resolved through `IsThisTargetBlocked` to
    become MetaGoals. Those visits use a throwaway walk, so the trail names
    only the nodes the real walk went through."""
    gd = _gd()
    resolution = resolve_root(make_state(level=15), gd, _objective(gd), _ctx(), None)
    assert resolution.trail.count("IsThisTargetBlocked") == 1


def test_the_chosen_root_is_never_repeated_as_its_own_alternative(monkeypatch):
    gd = _gd()
    gd._monster_level = {"chicken": 1}      # see the trunk test: without a
    gd._monster_type = {"chicken": "normal"}  # monster the patch is inert
    monkeypatch.setattr(tier_progress, "is_winnable", lambda s, g, c, h: True)
    resolution = resolve_root(_geared_state(), gd, _objective(gd), _ctx(), None)
    assert resolution.root == ReachCharLevel(level=20)
    # The trunk is the ROOT here, so it is not repeated as its own alternative;
    # the orphan skill root behind it still is one.
    assert resolution.alternatives == (ReachSkillLevel(skill="woodcutting", level=3),)
    assert resolution.trail == ("IsMyGearBehindMyTier", "IsThereACombatTarget",
                                "CanIClearMyTier")


def test_a_wall_still_offers_the_trunk_as_an_alternative(monkeypatch):
    gd = _gd()
    gd._monster_level = {"chicken": 1}
    gd._monster_type = {"chicken": "normal"}
    monkeypatch.setattr(tier_progress, "is_winnable", lambda s, g, c, h: False)
    resolution = resolve_root(_geared_state(), gd, _objective(gd), _ctx(), None)
    assert resolution.root is None
    # The wall is still `None` — the orphan skill roots are OFFERED behind the
    # trunk, they do not replace the wall verdict. `CanIClearMyTier`'s
    # docstring records the measurement that rejected putting them on this arm.
    assert resolution.alternatives == (ReachCharLevel(level=20),
                                       ReachSkillLevel(skill="woodcutting", level=3))


# ---------------------------------------------------------------------------
# The restored standalone skill root — `_orphan_skill_roots`
#
# `ef67c1d6` deleted four standalone `ReachSkillLevel` emitters on the premise
# "skills are pure prerequisites now". These tests state the rule that premise
# is false for, and the catalogue ones answer about the GAME rather than about
# a fixture.
# ---------------------------------------------------------------------------

def test_the_nameable_skills_are_exactly_those_with_an_equippable_recipe(
        bundle_game_data: GameData):
    """The rule's first conjunct, measured on the committed bundle.

    THREE skills put something on the gear sheet, so a gear target can name
    them through `GearTarget.blocking_skill`.

    This assertion used to read `{"alchemy", "gearcrafting", "jewelrycrafting",
    "weaponcrafting"}`, on the reasoning that 20 of alchemy's 25 recipes are
    `utility` items and `utility1_slot`/`utility2_slot` accept them. That
    reasoning restated `ITEM_TYPE_TO_SLOTS` instead of asking the gear sheet,
    and the gear sheet disagrees: `objective._gear_candidates_by_type` skips
    `stats.type_ == "utility"` outright (those slots are served by
    `utility_potion_targets`), so a gear target named alchemy in 0 of the 42
    scenarios and could never name one. The potion count is still asserted
    below — it is the fact that made the old reading defensible, and it is
    exactly what the fix had to look past. See
    `tests/test_ai/scenarios/test_alchemy_rung.py` for the whole finding."""
    nameable = _gear_nameable_skills(bundle_game_data)
    assert nameable == {"gearcrafting", "jewelrycrafting", "weaponcrafting"}
    potions = [code for code, stats in bundle_game_data.all_item_stats.items()
               if stats.crafting_skill == "alchemy" and stats.type_ == "utility"]
    assert len(potions) >= 20, potions


def test_the_rule_admits_the_five_skills_the_gear_sheet_never_ranks(
        bundle_game_data: GameData):
    """The rule, end to end, on a real scenario character: alchemy, cooking,
    fishing, mining and woodcutting — the five whose whole output the gear
    sheet declines (a `consumable`, a `resource`, or a `utility` potion).
    Cooking is the instance the epic named; the other four arrive because the
    rule is about the catalogue, not about cooking.

    `l1_fresh` is the tie case (every skill at the floor), so the order is
    `SKILL_NAMES` and alchemy leads by vocabulary rather than by gap."""
    state = census_state(SCENARIOS["l1_fresh"], bundle_game_data)
    roots = _orphan_skill_roots(state, bundle_game_data)
    assert [r.skill for r in roots] == ["alchemy", "cooking", "fishing",
                                        "mining", "woodcutting"]
    assert all(r.level == state.skills[r.skill] + 1 for r in roots)


def test_an_orphan_skill_with_no_open_rung_gets_no_root():
    """The rule's SECOND conjunct, and the reason it is not decoration. A root
    the planner cannot serve is the O1 census's `o1_silent_stall` residual —
    the exact failure this seam exists to prevent — so a skill with no open,
    XP-positive rung must produce NOTHING.

    This fixture's woodcutting has one rung (`ash_tree` -> `ash_wood`, level
    1). At woodcutting 50 that rung is deep in the server's zero-xp band and
    `LevelSkill.is_applicable` refuses, so the orphan tuple is empty even
    though woodcutting is still un-nameable by any gear target."""
    gd = _gd()
    assert "woodcutting" not in _gear_nameable_skills(gd)
    grinding = make_state(level=15, skills={"woodcutting": 2})
    assert [r.skill for r in _orphan_skill_roots(grinding, gd)] == ["woodcutting"]
    topped = make_state(level=15, skills={"woodcutting": 50})
    assert _orphan_skill_roots(topped, gd) == ()


def test_the_orphan_order_is_the_gap_to_the_character_level(
        bundle_game_data: GameData):
    """ONE INTEGER decides, and it is `skill level - character level` (the
    skill trailing furthest goes first). Two states over the same catalogue,
    differing only in WHICH orphan skill trails further, must swap the head —
    a fixed vocabulary order alone could not do that.

    `l1_fresh` is the tie case: every orphan is at the floor, every gap is
    equal, and the order falls to `SKILL_NAMES`, the API schema's own
    vocabulary, never `sorted()` as a decision key."""
    base = census_state(SCENARIOS["l1_fresh"], bundle_game_data)
    assert [r.skill for r in _orphan_skill_roots(base, bundle_game_data)] == [
        "alchemy", "cooking", "fishing", "mining", "woodcutting"]

    # alchemy, fishing and woodcutting are parked AT the character level so the
    # contest is cooking against mining and nothing else: a skill left at the
    # floor trails by 19 and would win both halves, which would prove nothing.
    parked = {"alchemy": 20, "fishing": 20, "woodcutting": 20}
    cook_ahead = replace(base, level=20,
                         skills={**base.skills, **parked,
                                 "cooking": 15, "mining": 5})
    assert _orphan_skill_roots(cook_ahead, bundle_game_data)[0].skill == "mining"
    mine_ahead = replace(base, level=20,
                         skills={**base.skills, **parked,
                                 "cooking": 5, "mining": 15})
    assert _orphan_skill_roots(mine_ahead, bundle_game_data)[0].skill == "cooking"


def test_cooking_is_a_root_the_walk_offers(bundle_game_data: GameData):
    """THE REGRESSION, DIRECTLY. Before this fix `resolve_root` could not yield
    `ReachSkillLevel(cooking, ...)` for ANY of the 42 scenarios: the sole
    producer was `IsThisTargetBlocked` off a gear target's crafting skill, and
    no cooking recipe produces an equippable. Now the fisher's own skill is a
    root the resolution offers — which is what
    `strategy_driver._resolve_step_goal` and `_servable_promotion` need in
    order to reach it at all."""
    state = census_state(SCENARIOS["l24_fisher_cooking_rung"], bundle_game_data)
    resolution = resolve_root(
        state, bundle_game_data,
        CharacterObjective.from_game_data(bundle_game_data), _ctx(), None)
    offered = [g for g in (resolution.root, *resolution.alternatives)
               if isinstance(g, ReachSkillLevel)]
    assert ReachSkillLevel(skill="cooking",
                           level=state.skills["cooking"] + 1) in offered


def test_the_orphan_roots_sit_behind_the_trunk(bundle_game_data: GameData):
    """The ORDER is the safety property, and it was measured rather than
    guessed. `objective_step_goal`'s `ReachCharLevel` arm runs
    `_marginal_provision_goal` FIRST, so the trunk slot is also how the
    objective's own provisioning gets planned; an orphan skill climb placed
    ahead of it displaced `GatherMaterials(mithril_bar)` at
    `l48_band_adequate` — the gear that breaks the L38-48 wall. Behind it, an
    orphan root is reached exactly when nothing else can be served."""
    state = census_state(SCENARIOS["l1_fresh"], bundle_game_data)
    alts = resolve_root(state, bundle_game_data,
                        CharacterObjective.from_game_data(bundle_game_data),
                        _ctx(), None).alternatives
    trunk = next(i for i, alt in enumerate(alts)
                 if isinstance(alt, ReachCharLevel))
    skills = [i for i, alt in enumerate(alts) if isinstance(alt, ReachSkillLevel)]
    assert skills, alts
    assert min(skills) > trunk
