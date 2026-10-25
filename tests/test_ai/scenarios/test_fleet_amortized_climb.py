"""Two characters, one skill climb (spec 2026-10-18 §2.5, acceptance §5.5).

Both characters have Robby's live shape (level 41, gearcrafting/jewelrycrafting
around 20) and miss `L*` pieces gated on gearcrafting 30 and jewelrycrafting 30
(`royal_skeleton_pants` and `_helmet`; `royal_skeleton_ring` x2 and
`lost_amulet`). Ana is the higher gearcrafter (23 against 20), Bea the higher
jewelrycrafter (25 against 22). Spec §2.5: one crafter per skill, chosen by the
least remaining climb, climbs for the whole fleet; the other publishes demand
and receives the piece by bank withdraw; neither picks an XP fight meanwhile.

Driven through production code end to end: `plan_from_state` computes each
objective, the coordination board carries both characters' pieces and skills,
`_update_coordination` decides the roles, and the plans are the real arbiter's.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.acquisition_cost import route_options
from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective_context import farm_target
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.learning.yield_reprs import grind_xp_repr
from artifactsmmo_cli.ai.obtain_model.policy import PIECE_POLICY
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.shared_world import shared_world
from tests.test_ai.test_gear_objective import _robby

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"
FLEET = ("Ana", "Bea")
"""The fleet order (`GET /my/characters`)."""
GEAR_PIECES = ("royal_skeleton_pants", "royal_skeleton_helmet")
"""Both characters' gearcrafting-30 `L*` pieces."""
CLIMBED = ("gearcrafting", "jewelrycrafting")


def _state(name: str, gearcrafting: int, jewelrycrafting: int, **kw: object) -> WorldState:
    """Robby's live shape under another name, with the two climbed skills set,
    the per-skill xp fields every live sheet carries (a climb is priced off
    `skill_max_xp`) and a level-41 bag (120 units, 30 slots: the fixture's
    20-unit bag cannot hold a gearcrafting grind's batch)."""
    robby = _robby()
    skills = {**robby.skills, "gearcrafting": gearcrafting,
              "jewelrycrafting": jewelrycrafting}
    return replace(robby, character=name, skills=skills,
                   skill_xp={skill: 0 for skill in skills},
                   skill_max_xp={skill: 1000 for skill in skills},
                   inventory_max=120, inventory_slots_max=30, **kw)


def _seed_history(db: str) -> None:
    """The fleet's recorded past, as the live DB holds it: both characters
    have ground both climbed skills (`ReachSkill(...)` cycles, 10 xp each)
    and served supply requests (`SupplyBank(...)` cycles), so climbs and the
    sibling route are priced from observation."""
    for name in FLEET:
        store = LearningStore(db_path=db, character=name)
        store.start_session()
        for i in range(10):
            for skill in CLIMBED:
                store.record_cycle(Cycle(
                    ts=f"2026-10-20T00:{i:02d}:00+00:00", session_id="s", cycle_index=i,
                    character=name, outcome="ok", selected_goal=f"ReachSkill({skill}->31)",
                    delta_skill_xp_json=json.dumps({skill: 10})))
            store.record_cycle(Cycle(
                ts=f"2026-10-20T01:{i:02d}:00+00:00", session_id="s", cycle_index=i,
                character=name, outcome="ok", selected_goal="SupplyBank(ash_plankx5)",
                delta_skill_xp_json=json.dumps({})))
        store.end_session(exit_reason="normal")
        store.close()


def _player(name: str, state: WorldState, db: str, gd: GameData) -> GamePlayer:
    player = GamePlayer(character=name, fleet_order=FLEET,
                        history=LearningStore(db_path=db, character=name))
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player._coordination = CoordinationStore(db_path=db, character=name)
    player.seed_offline(state, gd)
    return player


def _publish(player: GamePlayer, gd: GameData) -> None:
    """The publish half of `_update_coordination`, on its own: the skills and
    the missing pieces' closure, so both boards exist before either character
    decides a role (the live children publish every cycle; the order two of
    them first decide in is not what this file is about)."""
    assert player._coordination is not None and player.state is not None
    now = datetime.now(UTC)
    player._coordination.publish_skills(player.state.skills, now)
    player._coordination.publish_demand(player._own_unmet_demand(player.state, gd),
                                        frozenset(), now, player._own_piece_value())


@pytest.fixture
def fleet(tmp_path: Path) -> tuple[GamePlayer, GamePlayer, GameData]:
    """Ana (gearcrafting 23, jewelrycrafting 22) and Bea (20, 25): each plans
    once, both publish, then each decides its role on the full board."""
    gd = shared_world(BUNDLE)
    db = str(tmp_path / "fleet.db")
    _seed_history(db)
    ana = _player("Ana", _state("Ana", 23, 22), db, gd)
    bea = _player("Bea", _state("Bea", 20, 25), db, gd)
    for player in (ana, bea):
        player.plan_from_state()
    for player in (ana, bea):
        _publish(player, gd)
    for player in (ana, bea):
        assert player.state is not None
        player._update_coordination(player.state, gd)
    return ana, bea, gd


def test_both_characters_miss_the_gearcrafting_pieces(fleet) -> None:  # type: ignore[no-untyped-def]
    """The shape this file needs, pinned: both objectives miss the two
    gearcrafting-30 pieces, so the fleet demands gearcrafting 30."""
    ana, bea, gd = fleet
    for player in (ana, bea):
        missing = {piece.code for piece in player._last_ctx.gear_objective.missing}
        assert set(GEAR_PIECES) <= missing
        assert {gd.producing_requirement(code) for code in GEAR_PIECES} == {("gearcrafting", 30)}


def test_only_the_least_remaining_climber_takes_the_role(fleet) -> None:  # type: ignore[no-untyped-def]
    """Gearcrafting 23 against 20, demanded 30: the 23 claims `logger` (the
    role owning gearcrafting) and the 20 does not, though the board's
    gearcrafting demand is what weighs most on it too. Bea is the higher
    jewelrycrafter, so she is the fleet's jewelrycrafting climber."""
    ana, bea, _gd = fleet
    assert ana._role == "logger"
    assert bea._role is not None and bea._role != "logger"
    assert ana._fleet_climbers == bea._fleet_climbers == {
        "gearcrafting": "Ana", "jewelrycrafting": "Bea"}


def test_the_other_prices_the_gearcrafting_piece_by_the_sibling_climb(fleet) -> None:  # type: ignore[no-untyped-def]
    """Bea's gearcrafting pieces are served by a withdraw (Ana crafts and banks
    them). The sibling route's unlock is Ana's remaining climb, 23 -> 30 at
    1000 xp a level and 10 xp a cycle (700 cycles), shared by the three units
    it opens (this piece and Ana's own two) and rounded up (234), plus the
    fleet's median request (10 cycles): far below Bea's own climb from 20
    (1000 cycles)."""
    _ana, bea, gd = fleet
    bea.plan_from_state()
    ctx = bea._last_ctx
    pieces = {piece.code: piece for piece in ctx.gear_objective.missing}
    for code in GEAR_PIECES:
        assert pieces[code].route is SourceKind.WITHDRAW
    assert bea.state is not None
    routes = route_options("royal_skeleton_pants", bea.state, gd, ctx, bea.history,
                           policy=PIECE_POLICY)
    unlocks = {route.unlock: route.unlock_actions for route in routes}
    assert unlocks["sibling:royal_skeleton_pants"] == 234 + 10
    assert unlocks["skill:gearcrafting:30"] == 1000


def test_the_other_receives_by_withdraw(fleet) -> None:  # type: ignore[no-untyped-def]
    """Ana banks the pants with a supply claim: Bea's plan withdraws them and
    puts them on."""
    ana, bea, gd = fleet
    assert ana._coordination is not None and bea.state is not None
    ana._coordination.claim_supply("royal_skeleton_pants", datetime.now(UTC))
    bea.seed_offline(replace(bea.state, bank_items={"royal_skeleton_pants": 1}), gd)
    report = bea.plan_from_state()
    steps = [repr(action) for action in report.plan]
    withdraw = next(i for i, step in enumerate(steps)
                    if step.startswith("Withdraw") and "royal_skeleton_pants" in step)
    assert any(step.startswith("Equip") and "royal_skeleton_pants" in step
               for step in steps[withdraw + 1:]), steps


def test_neither_picks_an_xp_fight(fleet) -> None:  # type: ignore[no-untyped-def]
    """Neither root is a character level and neither plan grinds XP: the
    crafter climbs its skill, the other climbs the skill it is the climber
    for."""
    ana, bea, _gd = fleet
    for player in (ana, bea):
        report = player.plan_from_state()
        assert not isinstance(report.decision.chosen_root, ReachCharLevel)
        assert repr(report.selected_goal) != grind_xp_repr(player._last_ctx.gear_objective.monster)
        assert not repr(report.selected_goal).startswith("GrindCharacterXP")
    assert ana.plan_from_state().decision.chosen_root == ReachSkillLevel("gearcrafting", 24)
    assert bea.plan_from_state().decision.chosen_root == ReachSkillLevel("jewelrycrafting", 26)


def test_a_crafter_with_own_l_star_held_still_serves_the_fleet(fleet) -> None:  # type: ignore[no-untyped-def]
    """Ana holds the logger role and her own `L*` is held, but Bea's
    gearcrafting pieces are still on the board: Ana's root is their climb,
    never `ReachCharLevel`, the trunk is not offered, and no grind target is
    named. Ana's real cycle context, with her objective held."""
    ana, _bea, gd = fleet
    assert ana.state is not None
    ana.plan_from_state()
    ctx = ana._last_ctx
    assert {piece.code for piece in ctx.fleet_pieces} == set(GEAR_PIECES)
    held = replace(ctx.gear_objective, missing=())
    resolution = resolve_root(ana.state, gd, CharacterObjective.from_game_data(gd),
                              replace(ctx, gear_objective=held), ana.history)
    assert resolution.root == ReachSkillLevel("gearcrafting", 24)
    assert not any(isinstance(alt, ReachCharLevel) for alt in resolution.alternatives)
    assert farm_target(None, held, bool(ctx.fleet_pieces)) is None
