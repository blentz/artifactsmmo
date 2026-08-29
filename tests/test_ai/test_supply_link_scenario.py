"""The supply link, end to end: a blocked character ASKS and a sibling answers.

THE CHAIN THIS PROVES, and it had never once run. Measured on the live fleet
(`learning.db`, 105,159 cycles across five characters):

    SupplyBank actions executed .................. 0
    supply_claims rows ........................... 0
    demand rows on the board ..................... 4, every one quantity 1
                                                    and self_servable

Not "rarely" — never, in the whole durable history, while 41% of every cycle the
fleet spent went into `LevelSkill` and all five characters independently climbed
gearcrafting, weaponcrafting and jewelrycrafting.

THE PLUMBING WAS NEVER THE PROBLEM. Leases, the skill ledger, the demand board,
the four claim kinds, `SupplyBankGoal` — all of it works and all of it was idle,
because the REQUEST was never made: demand is published from the chosen root, a
character blocked by a crafting-skill gate resolves to `ReachSkillLevel` (which
names no item), so it published nothing at all. The one item a sibling could have
made was the one item never asked for.

So the walk now records the target its skill gate rejected
(`RootWalk.blocked_target`) and the player publishes it. `serves_item` marks it
NOT self-servable — the asker's own gate is what blocked it — which is exactly
what makes the request ASYMMETRIC, and `SUPPLY_BANK`'s second arm fires on any
size of asymmetric demand.

This file drives BOTH halves through production code on the committed bundle:
`resolve_root` for the ask, `_update_coordination` for the publish, and the real
means ladder plus `map_means` for the answer. The unit tests either side of it
(`test_decisions_root`, `test_player_coordination`) pin the halves; this pins
that they meet.
"""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from artifactsmmo_cli.ai.goals.supply_bank import SupplyBankGoal
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import (
    SCENARIOS,
    load_bundle_game_data,
    scenario_state,
)
from artifactsmmo_cli.ai.strategy_driver import map_means
from artifactsmmo_cli.ai.tiers.means import MeansKind, _fires
from artifactsmmo_cli.ai.world_state import WorldState

BUNDLE = Path(__file__).resolve().parent / "scenarios" / "fixtures" / "gamedata_bundle.json"

ASKED = "life_amulet"
"""What the asker cannot make. `l12_deep_chain_grind` holds jewelrycrafting 2
against this amulet's gate of 5, so the walk answers with a climb and the amulet
is what it drops — see `test_decisions_root`'s pin on `blocked_target`."""

NOW = datetime.now(timezone.utc)
"""Computed at import, not a fixed stamp: every coordination row expires
`DEMAND_TTL_SECONDS` after the `now` it was published with, so a hardcoded past
timestamp is already stale when the reader's own `datetime.now(utc)` runs."""


def _game_data():
    return load_bundle_game_data(BUNDLE)


def _asker(db: str, gd) -> GamePlayer:
    """The blocked character, driven through the REAL walk.

    `plan_from_state` is what sets `_last_blocked_target` (via
    `_record_decision_targets`, the one producer both it and `_decide_band`
    share), so the ask is derived here rather than hand-set — a hand-set field
    would pass this test against a walk that had stopped recording anything."""
    state = replace(scenario_state(SCENARIOS["l12_deep_chain_grind"], gd),
                    character="Ask")
    player = GamePlayer(character="Ask")
    player._coordination = CoordinationStore(db_path=db, character="Ask")
    player.seed_offline(state, gd)
    player.plan_from_state()
    player._update_coordination(player.state, gd)
    return player


def _supplier_state(gd) -> WorldState:
    """A sibling who CAN make the amulet: jewelrycrafting 10 against its gate of
    5. Everything else is the asker's own scenario, so the only difference
    between the two characters is the skill the whole feature turns on."""
    state = scenario_state(SCENARIOS["l12_deep_chain_grind"], gd)
    skills = dict(state.skills)
    skills["jewelrycrafting"] = 10
    return replace(state, character="Sup", skills=skills)


def _supplier(db: str, gd) -> GamePlayer:
    player = GamePlayer(character="Sup")
    player._coordination = CoordinationStore(db_path=db, character="Sup")
    player.seed_offline(_supplier_state(gd), gd)
    player._update_coordination(player.state, gd)
    return player


def test_the_blocked_ask_reaches_a_sibling_who_can_serve_it(tmp_path) -> None:
    """THE WHOLE CHAIN: ask -> board -> asymmetry -> role -> supply target ->
    the rung fires -> a goal that produces the thing.

    Each assertion is a link that was intact but unreachable before the ask
    existed, so a break anywhere reports at the link that broke rather than as
    one opaque failure at the end."""
    db = str(tmp_path / "coord.db")
    gd = _game_data()

    asker = _asker(db, gd)
    # LINK 1 — the ask exists at all. This is the assertion the live fleet fails:
    # a blocked character published `{}` and the board stayed empty.
    assert asker._last_blocked_target == ASKED
    published = asker._own_unmet_demand(asker.state, gd)
    assert ASKED in published

    # LINK 2 — and it is published as ASYMMETRIC. `serves_item` fails on the
    # asker's own gate, so the code is absent from `self_servable`, which is the
    # only thing that makes `SUPPLY_BANK`'s second arm reachable at quantity 1.
    board = CoordinationStore(db_path=db, character="Reader")
    assert ASKED in board.sibling_demand(NOW)
    assert ASKED in board.sibling_demand_asymmetric(NOW)

    supplier = _supplier(db, gd)
    # LINK 3 — the sibling reads the asymmetry and elects a role that owns the
    # skill (`jeweler` is the catalog's jewelrycrafting owner).
    assert ASKED in supplier._asymmetric_demand
    assert supplier._role is not None

    # LINK 4 — and picks THAT item to produce, not one of its materials: the
    # asymmetric request outranks every symmetric one regardless of size.
    assert supplier._supply_target is not None
    assert supplier._supply_target[0] == ASKED

    # LINK 5 — the rung fires at quantity 1, which the bulk gate alone would
    # have refused (SUPPLY_DEMAND_MIN is 10 and every live request is 1).
    ctx = supplier._selection_context(None)
    assert ctx.supply_target is not None
    assert ctx.supply_target[2] < 10
    assert _fires(MeansKind.SUPPLY_BANK, supplier.state, gd, None, ctx)

    # LINK 6 — and the goal it maps to is the one that banks the item.
    goal = map_means(MeansKind.SUPPLY_BANK, gd, ctx, supplier.state, None, None)
    assert isinstance(goal, SupplyBankGoal)
    assert ASKED in repr(goal)


def test_a_sibling_without_the_skill_is_not_recruited(tmp_path) -> None:
    """The asymmetry must not advertise help nobody can give.

    `serves_item` is the ONE level gate, read by the asker's self-servable
    computation and by `_pick_supply_target` alike — so a sibling at the asker's
    own level answers no better than the asker does, and must not be handed the
    request. Without this the rung would fire on a character that cannot craft
    the item, which is the same stall by a longer route."""
    db = str(tmp_path / "coord.db")
    gd = _game_data()
    _asker(db, gd)

    player = GamePlayer(character="Sup")
    player._coordination = CoordinationStore(db_path=db, character="Sup")
    # Same jewelrycrafting 2 as the asker: reads the ask, cannot serve it.
    player.seed_offline(
        replace(scenario_state(SCENARIOS["l12_deep_chain_grind"], gd),
                character="Sup"), gd)
    player._update_coordination(player.state, gd)

    assert ASKED in player._asymmetric_demand
    assert player._supply_target is None or player._supply_target[0] != ASKED
