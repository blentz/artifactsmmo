"""The root walk's entry (spec 2026-10-18 §2.4): the next missing `L*` piece is
the root, and only a held `L*` grinds character XP.

`WhichPieceIsNext` reads the cycle's `ctx.gear_objective`: while a piece is
missing, the first piece whose step can be served heads the walk (through
`IsThisTargetBlocked`: a crafting-skill gate is its `ReachSkillLevel`, a
material its `ObtainItem`); a declined piece is named in `declined`; once every
piece is held the root is one more character level. No objective is the wall.
"""

from collections import Counter
from dataclasses import replace
from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.acquisition_cost import EQUIP_ACTIONS, cheapest_route
from artifactsmmo_cli.ai.decisions.root import (
    IsThisTargetBlocked,
    RootResolution,
    RootWalk,
    resolve_root,
)
from artifactsmmo_cli.ai.decisions.which_piece_is_next import WhichPieceIsNext
from artifactsmmo_cli.ai.fleet_piece import FleetPiece
from artifactsmmo_cli.ai.fleet_work import FLEET_SUPPLY
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective import gear_objective
from artifactsmmo_cli.ai.gear_objective_context import farm_target
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.obtain_model.policy import PIECE_POLICY
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.progression_reserve import spendable_pocket
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachFleetOutcome,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
from tests.test_ai.shared_world import shared_world
from tests.test_ai.test_decisions_root import _gd
from tests.test_ai.test_gear_objective import BUNDLE, COPPER, CTX, _novice, _robby
from tests.test_ai.test_strategy_driver import _ctx

SHIELD = GearPiece("shield_slot", "iron_shield", 0, Fraction(3), Fraction(10), SourceKind.CRAFT)
"""Gearcrafting 10 on a gearcrafting-1 character: skill-gated."""
CLUB = GearPiece("weapon_slot", "ash_club", 0, Fraction(2), Fraction(10), SourceKind.CRAFT)
"""Its ash_plank chain is gatherable: attainable."""
LEGS = GearPiece("leg_armor_slot", "leather_legs", 1, Fraction(1), Fraction(10), SourceKind.CRAFT)
"""Leather has no source: material-gated on `leather`."""


def _missing(*pieces: GearPiece) -> GearObjective:
    return GearObjective("wolf", {piece.slot: piece.code for piece in pieces},
                         Fraction(1), pieces)


def _resolve(state: WorldState, gd: GameData, objective: GearObjective | None,
             decline: dict[MetaGoal, str] | None = None,
             ctx: SelectionContext | None = None) -> RootResolution:
    reasons = decline or {}
    return resolve_root(state, gd, CharacterObjective.from_game_data(gd),
                        replace(ctx or _ctx(), gear_objective=objective), None,
                        lambda root: reasons.get(root))


def test_the_first_missing_piece_is_the_root() -> None:
    """Missing order is the objective's own (layer, then gain per price): the
    walk never re-sorts it. The skill-gated shield's step is the next
    gearcrafting level, and its code is the published demand."""
    gd = _gd()
    resolution = _resolve(make_state(level=15), gd, _missing(SHIELD, CLUB, LEGS))
    assert resolution.root == ReachSkillLevel(skill="gearcrafting", level=2)
    assert resolution.trail == ("WhichPieceIsNext", "IsThisTargetBlocked")
    assert resolution.blocked_target == "iron_shield"
    assert resolution.alternatives[:2] == (
        ObtainItem("ash_club", 1, slot="weapon_slot"), ObtainItem("leather", 2))


def test_a_zero_gain_piece_keeps_its_place() -> None:
    """A deferred Task 3 note: the within-layer gain can be 0. The walk takes
    the objective's order as given, so a zero-gain piece listed first heads it."""
    gd = _gd()
    flat = replace(CLUB, gain=Fraction(0))
    resolution = _resolve(make_state(level=15), gd, _missing(flat, SHIELD))
    assert resolution.root == ObtainItem("ash_club", 1, slot="weapon_slot")


def test_a_declined_piece_yields_to_the_next() -> None:
    """An unserved first piece cannot head the walk: the second piece is the
    root, the first is named in `declined` with its reason and stays on offer."""
    gd = _gd()
    shield_step = ReachSkillLevel(skill="gearcrafting", level=2)
    resolution = _resolve(make_state(level=15), gd, _missing(SHIELD, CLUB, LEGS),
                          {shield_step: "no workshop"})
    assert resolution.root == ObtainItem("ash_club", 1, slot="weapon_slot")
    assert resolution.declined == ((repr(shield_step), "no workshop"),)
    assert resolution.blocked_target is None
    assert resolution.alternatives[:2] == (shield_step, ObtainItem("leather", 2))


def test_every_piece_declined_offers_the_trunk() -> None:
    """Ruling AI (final review F1), INTERIM until Plan B makes the obtain model
    and the walk agree: with no servable gear step, the next action that best
    advances the character is XP, so the root is one more character level.
    Every piece stays on offer behind its named reason, ahead of the trunk's
    alternatives — the trunk is the root, never repeated as an alternative."""
    gd = _gd()
    shield_step = ReachSkillLevel(skill="gearcrafting", level=2)
    club_step = ObtainItem("ash_club", 1, slot="weapon_slot")
    resolution = _resolve(make_state(level=15), gd, _missing(SHIELD, CLUB),
                          {shield_step: "a", club_step: "b"})
    assert resolution.root == ReachCharLevel(level=16)
    assert resolution.declined == ((repr(shield_step), "a"), (repr(club_step), "b"))
    assert resolution.alternatives[:2] == (shield_step, club_step)
    assert not any(isinstance(alt, ReachCharLevel) for alt in resolution.alternatives)


def test_a_declined_objective_grinds_its_monster() -> None:
    """Ruling AI: the trunk offered behind every declined piece fights `m*`.
    `farm_target` names no grind target while a piece is missing, so the
    trunk's step reads the objective's monster instead of returning None."""
    gd = _gd()
    ctx = replace(_ctx(combat_monster=None), gear_objective=_missing(SHIELD))
    goal = objective_step_goal(ReachCharLevel(level=16), make_state(level=15), gd, ctx)
    assert repr(goal) == "GrindCharacterXP(wolf)"
    assert objective_step_goal(ReachCharLevel(level=16), make_state(level=15), gd,
                               replace(ctx, gear_objective=None)) is None


def test_held_objective_grinds_the_next_level() -> None:
    """§2.4.1: every slot holds its `L*` item, so the root is one more
    character level, fought on `m*` — no milestone."""
    gd = _gd()
    resolution = _resolve(make_state(level=15), gd, _missing())
    assert resolution.root == ReachCharLevel(level=16)
    assert resolution.trail == ("WhichPieceIsNext",)
    assert ReachCharLevel(level=16) not in resolution.alternatives


def test_no_objective_is_the_wall() -> None:
    """No achievable loadout pays XP on any monster: no root, and no trunk on
    offer either — there is nothing to grind it on."""
    gd = _gd()
    resolution = _resolve(make_state(level=15), gd, None)
    assert resolution.root is None
    assert not any(isinstance(alt, ReachCharLevel) for alt in resolution.alternatives)


def test_the_node_reads_only_the_context_objective() -> None:
    """The node itself: a missing piece resolves through `IsThisTargetBlocked`
    on the same walk to the piece's step (resolved in the node, so a
    prospecting item can precede its drop work: plan B Task 12b), held to the
    next level, none to None."""
    gd = _gd()
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=15)
    walk = RootWalk()
    child = WhichPieceIsNext(objective, walk).resolve(
        state, gd, replace(_ctx(), gear_objective=_missing(CLUB)), None)
    assert child == ObtainItem("ash_club", 1, slot="weapon_slot")
    assert walk.trail == ["WhichPieceIsNext", "IsThisTargetBlocked"]
    assert WhichPieceIsNext(objective, RootWalk()).resolve(
        state, gd, replace(_ctx(), gear_objective=_missing()), None) == ReachCharLevel(16)
    assert WhichPieceIsNext(objective, RootWalk()).resolve(
        state, gd, _ctx(), None) is None


@pytest.fixture(scope="module")
def bundle() -> GameData:
    return shared_world(BUNDLE)


def test_robby_climbs_or_builds_never_waits(bundle: GameData) -> None:
    """Spec §5.1: Robby's live shape (level 41, L10-20 armour, gearcrafting 23,
    jewelrycrafting 22, weaponcrafting 22, an items task held). The root is an
    `L*` piece or the crafting climb in front of one — never None, and no level
    grind is offered while a piece is missing."""
    state = replace(_robby(), task_code="ash_plank", task_type="items",
                    task_total=50, task_progress=0)
    objective = gear_objective(state, bundle, CTX, None)
    assert objective is not None and objective.missing
    resolution = _resolve(state, bundle, objective, ctx=CTX)
    codes = {piece.code for piece in objective.missing}
    root = resolution.root
    assert isinstance(root, ObtainItem | ReachSkillLevel), root
    if isinstance(root, ReachSkillLevel):
        assert resolution.blocked_target in codes
        stats = bundle.item_stats(resolution.blocked_target)
        assert stats is not None and stats.crafting_skill == root.skill
    else:
        assert root.code in codes or any(
            root.code in (bundle.crafting_recipe(code) or {}) for code in codes)
    assert not any(isinstance(alt, ReachCharLevel) for alt in resolution.alternatives)


def _wearing_its_target(gd: GameData, level: int) -> WorldState:
    """The level-`level` novice wearing its own `L*`, the copper it replaced
    carried."""
    target = gear_objective(_novice(gd, level=level), gd, CTX, None)
    assert target is not None
    carried = Counter(COPPER.values())
    carried.subtract(Counter(target.loadout.values()))
    return _novice(gd, equipment=target.loadout, inventory=+carried, level=level)


def test_a_level_up_retargets_without_an_xp_fight(bundle: GameData) -> None:
    """Review Focus 3: at level 14 the novice holds its `L*` and grinds the
    next level; at 15 the level-15 gear is legal, `L*` moves, and the very next
    root is its first new piece — no level grind in between or on offer."""
    held = _wearing_its_target(bundle, 14)
    before = gear_objective(held, bundle, CTX, None)
    assert before is not None and before.held
    assert _resolve(held, bundle, before, ctx=CTX).root == ReachCharLevel(level=15)

    levelled = replace(held, level=15)
    after = gear_objective(levelled, bundle, CTX, None)
    assert after is not None and after.missing
    first = after.missing[0]
    assert (stats := bundle.item_stats(first.code)) is not None and stats.level == 15
    resolution = _resolve(levelled, bundle, after, ctx=CTX)
    gear = CharacterObjective.from_game_data(bundle).classify_target(first.code, levelled)
    assert resolution.root == IsThisTargetBlocked(first.slot, gear, RootWalk()).resolve(
        levelled, bundle, CTX, None)
    assert not any(isinstance(alt, ReachCharLevel) for alt in resolution.alternatives)


def test_the_held_cell_grinds_exactly_the_next_level(bundle: GameData) -> None:
    """Ruling Y: the one catalogued scenario that wears its own `L*`. Its
    objective is held, so the root is exactly `ReachCharLevel(level + 1)` —
    and the live cycle grinds `m*` for it. Since spec 2026-10-18 §2.9 its
    `L*` is the set that kills `blue_slime` fastest (the scenario wears it)."""
    state = scenario_state(SCENARIOS["l14_wears_its_target"], bundle)
    objective = gear_objective(state, bundle, CTX, None)
    assert objective is not None and objective.held
    assert objective.monster == "blue_slime"
    assert _resolve(state, bundle, objective, ctx=CTX).root == ReachCharLevel(level=15)
    player = GamePlayer(character="l14_wears_its_target", history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(state, bundle)
    report = player.plan_from_state()
    assert report.decision.chosen_root == ReachCharLevel(level=15)
    assert repr(report.selected_goal) == "GrindCharacterXP(blue_slime)"


def test_a_piece_the_catalogue_does_not_know_is_refused() -> None:
    """API data or fail (ruling AF): an objective naming an item the
    decision's game data does not know raises, by name, before any piece is
    classified — even when a known piece comes first."""
    gd = _gd()
    ghost = GearPiece("helmet_slot", "no_such_helmet", 0, Fraction(1), Fraction(1), SourceKind.CRAFT)
    with pytest.raises(ValueError, match=r"\['no_such_helmet'\], absent from game data"):
        _resolve(make_state(level=15), gd, _missing(CLUB, ghost))


def test_no_trunk_at_the_level_cap() -> None:
    """Final review F12: at the API's level cap (`GameData.max_character_level`)
    no `ReachCharLevel` is offered, held or behind declined pieces — it could
    never be satisfied, and the character would grind `m*` for XP the game no
    longer awards. One level below the cap the trunk is still offered."""
    gd = _gd()
    cap = gd.max_character_level
    held = _resolve(make_state(level=cap), gd, _missing())
    assert held.root is None
    assert not any(isinstance(alt, ReachCharLevel) for alt in held.alternatives)
    club_step = ObtainItem("ash_club", 1, slot="weapon_slot")
    declined = _resolve(make_state(level=cap), gd, _missing(CLUB), {club_step: "b"})
    assert declined.root is None
    assert declined.alternatives[:1] == (club_step,)
    assert _resolve(make_state(level=cap - 1), gd, _missing()).root == ReachCharLevel(level=cap)


# --- plan B Task 3: a piece is served by the route that priced it ------------

@pytest.mark.parametrize("route", [SourceKind.BUY, SourceKind.GE_FILL])
def test_a_bought_piece_is_never_a_climb(route: SourceKind) -> None:
    """A piece the book or a vendor priced is bought, not climbed to: the
    shield's gearcrafting 10 is unmet at 1, yet the root is the shield itself,
    slotted, and no crafting demand is published. Behind another piece, the
    alternative it offers is the same `ObtainItem`."""
    gd = _gd()
    state = make_state(level=15)
    bought = replace(SHIELD, route=route)
    shield = ObtainItem("iron_shield", 1, slot="shield_slot")
    first = _resolve(state, gd, _missing(bought, CLUB))
    assert (first.root, first.blocked_target) == (shield, None)
    behind = _resolve(state, gd, _missing(CLUB, bought))
    assert behind.root == ObtainItem("ash_club", 1, slot="weapon_slot")
    assert behind.alternatives[:1] == (shield,)


def test_a_crafted_piece_still_climbs() -> None:
    """A piece its craft priced keeps its crafting gate in front: the next
    gearcrafting level, its code the published demand, and the same climb among
    the alternatives behind another piece."""
    gd = _gd()
    state = make_state(level=15)
    climb = ReachSkillLevel(skill="gearcrafting", level=state.skills.get("gearcrafting", 1) + 1)
    first = _resolve(state, gd, _missing(SHIELD))
    assert (first.root, first.blocked_target) == (climb, "iron_shield")
    assert _resolve(state, gd, _missing(CLUB, SHIELD)).alternatives[:1] == (climb,)


def test_cheapest_route_matches_the_price(bundle: GameData) -> None:
    """One pricer: for each missing piece of Robby's objective, the piece's
    own price and route are `cheapest_route`'s answer plus the equip (ruling
    T3e m6a: `acquisition_actions` is `cheapest_route` by construction, so
    only the piece's fields are asked)."""
    state = _robby()
    objective = gear_objective(state, bundle, CTX, None)
    assert objective is not None and objective.missing
    for piece in objective.missing:
        price, route = cheapest_route(
            piece.code, 1, state, bundle, CTX, None, policy=PIECE_POLICY,
            pocket=spendable_pocket(state, bundle, frozenset({piece.code})))
        assert (Fraction(price + EQUIP_ACTIONS), route) == (piece.price, piece.route), piece



# ---------------------------------------------------------------------------
# A crafter's fleet pieces join its own (spec 2026-10-18 §2.5)
# ---------------------------------------------------------------------------

FLEET_SHIELD = FleetPiece("iron_shield", "gearcrafting", 10, Fraction(3))
"""A sibling's gearcrafting-10 piece on the board, for a gearcrafting-1 crafter."""


def _crafting(fleet: tuple[FleetPiece, ...] = (FLEET_SHIELD,), **kw) -> SelectionContext:
    return replace(_ctx(role="logger", **kw), fleet_pieces=fleet)


def test_a_crafter_holding_its_own_l_star_climbs_for_the_fleet() -> None:
    """Its own `L*` is held, but a sibling's piece its role skill makes is on
    the board: the root is that piece's climb, never one more character level,
    and the trunk is not even an alternative."""
    gd = _gd()
    resolution = _resolve(make_state(level=15), gd, _missing(), ctx=_crafting())
    assert resolution.root == ReachSkillLevel(skill="gearcrafting", level=2)
    assert not any(isinstance(alt, ReachCharLevel) for alt in resolution.alternatives)


def test_a_met_gate_serves_the_fleet_piece_by_the_supply_run() -> None:
    """At gearcrafting 10 the shield is one craft away, and it is the role's
    due supply target: the step banks it for the receivers."""
    gd = _gd()
    state = make_state(level=15, skills={**make_state().skills, "gearcrafting": 10})
    ctx = _crafting(supply_target=("iron_shield", 1, 1),
                    asymmetric_demand=frozenset({"iron_shield"}))
    resolution = _resolve(state, gd, _missing(), ctx=ctx)
    assert resolution.root == ReachFleetOutcome(FLEET_SUPPLY, "iron_shield")


def test_a_met_gate_not_yet_the_supply_target_is_crafted() -> None:
    """Ruling T7d M3: the gate is met but the role's supply run is for another
    item. The piece is still a step — its craft, one unit, which the supply
    run then banks — never no root, and no XP fight either."""
    gd = _gd()
    state = make_state(level=15, skills={**make_state().skills, "gearcrafting": 10})
    resolution = _resolve(state, gd, _missing(),
                          ctx=_crafting(supply_target=("ash_club", 1, 1),
                                        asymmetric_demand=frozenset({"ash_club"})))
    assert resolution.root == ObtainItem("iron_shield", 1)
    assert not any(isinstance(alt, ReachCharLevel) for alt in resolution.alternatives)


def test_a_declined_fleet_step_yields_and_withholds_the_trunk() -> None:
    """The climb's step is declined: recorded by name, and no XP fight follows
    even though every own piece is held."""
    gd = _gd()
    climb = ReachSkillLevel(skill="gearcrafting", level=2)
    resolution = _resolve(make_state(level=15), gd, _missing(), {climb: "no_plan"},
                          ctx=_crafting())
    assert resolution.root is None
    assert dict(resolution.declined) == {repr(climb): "no_plan"}


def test_fleet_and_own_pieces_share_one_order() -> None:
    """One `piece_order_key` over both: a fleet piece whose summed gain per
    price beats the crafter's own piece goes first, and a zero-gain fleet piece
    goes after it."""
    gd = _gd()
    rich = FleetPiece("iron_shield", "gearcrafting", 10, Fraction(10**9))
    poor = FleetPiece("iron_shield", "gearcrafting", 10, Fraction(0))
    club = _missing(CLUB)
    assert _resolve(make_state(level=15), gd, club, ctx=_crafting((rich,))).root == \
        ReachSkillLevel(skill="gearcrafting", level=2)
    first = _resolve(make_state(level=15), gd, club, ctx=_crafting((poor,)))
    assert first.root == ObtainItem("ash_club", 1, slot="weapon_slot")
    assert ReachSkillLevel(skill="gearcrafting", level=2) in first.alternatives


def test_no_fleet_piece_keeps_the_held_trunk() -> None:
    """A crafter whose role serves nothing on the board grinds as before."""
    gd = _gd()
    resolution = _resolve(make_state(level=15), gd, _missing(), ctx=_crafting(()))
    assert resolution.root == ReachCharLevel(level=16)


def test_waiting_fleet_demand_names_no_grind_target() -> None:
    """`L*` held, but fleet pieces wait: no monster is the grind target."""
    held = _missing()
    assert farm_target(None, held, False) == "wolf"
    assert farm_target(None, held, True) is None


AWAITED = replace(SHIELD, route=SourceKind.WITHDRAW)
"""The shield priced by the sibling route: a fleet crafter makes and banks it."""


def test_a_piece_a_sibling_crafts_waits_for_the_bank() -> None:
    """§2.5 "Delivery": the shield is served by a withdraw and the bank holds
    none yet, so it has no step — never this character's own gearcrafting
    climb — and the next piece heads the walk; nor is it offered as an
    alternative."""
    gd = _gd()
    shield = ObtainItem("iron_shield", 1, slot="shield_slot")
    resolution = _resolve(make_state(level=15, bank_items={}), gd, _missing(AWAITED, CLUB))
    assert resolution.root == ObtainItem("ash_club", 1, slot="weapon_slot")
    assert dict(resolution.declined) == {repr(shield): "awaits the fleet crafter"}
    assert shield not in resolution.alternatives
    assert ReachSkillLevel(skill="gearcrafting", level=2) not in resolution.alternatives


def test_a_banked_piece_from_a_sibling_is_withdrawn() -> None:
    """Once the crafter banks it, the shield is its own root: the step
    withdraws and equips it."""
    gd = _gd()
    state = make_state(level=15, bank_items={"iron_shield": 1})
    resolution = _resolve(state, gd, _missing(AWAITED, CLUB))
    assert resolution.root == ObtainItem("iron_shield", 1, slot="shield_slot")
