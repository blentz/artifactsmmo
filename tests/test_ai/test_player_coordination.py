"""Wire cross-character role coordination into the per-cycle player loop
(emergent-specialization spec, Task 11).

`GamePlayer._update_coordination` is the seam: called once per cycle in
`run()` beside `self._regear_edge.update(...)`, it renews this character's
lease, publishes its own unmet closure demand, re-decides its role, and
recomputes `self._supply_target` — which `_selection_context` threads onto
`SelectionContext.supply_target` for the SUPPLY_BANK means (Tasks 9/10) to
read.

Coverage note: this project's coverage config sets `branch = false`, so every
conditional added by this task needs a test pinned to EACH outcome, not just
one execution reaching the line. See the paired tests below (`..._none`/
`..._some`, `..._without_role`/`..._with_role`, etc.).
"""

import io
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import text
from sqlmodel import Session as SqlSession
from sqlmodel import select

from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.actions.ge_cancel_order import GeCancelOrderAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, RoleChange
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.supply_bank import SupplyBankGoal
from artifactsmmo_cli.ai.learning.coordination_store import (
    BANK_CLAIM_TTL_SECONDS,
    GE_ORDER_CLAIM_TTL_SECONDS,
    CoordinationStore,
)
from artifactsmmo_cli.ai.learning.models import MaterialDemand
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.role_catalog import ROLE_CATALOG
from artifactsmmo_cli.ai.role_selection import (
    ROLE_IDLE_DWELL_CYCLES,
    ROLE_MIN_HOLD_CYCLES,
    ROLE_UNSERVABLE_CYCLES,
    decide_role,
    demand_by_role,
)
from artifactsmmo_cli.ai.strategy_driver import map_means
from artifactsmmo_cli.ai.supply_batch_target import supply_batch_target_pure
from artifactsmmo_cli.ai.thresholds import SUPPLY_BATCH
from artifactsmmo_cli.ai.tiers.means import SUPPLY_DEMAND_MIN, MeansKind, _fires
from artifactsmmo_cli.rate_limited_error import RateLimitedError
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import (
    make_api_result,
    make_char_schema,
    make_get_character_result,
)
from tests.test_ai.test_role_selection import _LOR_SKILLS, _ROBBY_SKILLS
from tests.test_ai.test_strategy_driver import _make_planner_gd

_T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)
NOW = datetime.now(tz=timezone.utc)
"""Module-scope UTC instant for the supply-claim tests (`ai/supply_claim_and_batch`
Task 3) below — `CoordinationStore` rejects naive datetimes. Real wall-clock
time, not a fixed literal: `_pick_supply_target` stamps its OWN claim reads
and writes with `datetime.now(tz=timezone.utc)`, so a fixed past/future `NOW`
would read as already-expired against `DEMAND_TTL_SECONDS` (600s)."""


# ---------------------------------------------------------------------------
# Tasks 2-7 composition (from the brief): the cold-start allocator converges
# two characters wanting the same top-demand role onto DISTINCT roles.
# ---------------------------------------------------------------------------

def test_two_stores_converge_on_distinct_roles(tmp_path) -> None:
    """Cold start, end to end over the real store: two characters whose unmet
    needs point at DIFFERENT skills specialize apart.

    Nothing serializes them any more — the UNIQUE(`role`) constraint that used
    to is gone, and both claims would succeed even on the same role. They
    diverge because `sibling_demand` excludes self, so each one is ranking the
    OTHER's need: HAL wants copper_bar (mining), so C3P0 reads `miner`, and
    vice versa. That is demand doing the allocating, which is the point —
    exclusivity was never what made this case work."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    try:
        hal.publish_demand({"copper_bar": 10}, frozenset(), _T0)
        c3po.publish_demand({"ash_plank": 4}, frozenset(), _T0)
        skills = {"copper_bar": "mining", "ash_plank": "woodcutting"}

        held: dict[str, str] = {}
        for store in (hal, c3po):
            by_role = demand_by_role(store.sibling_demand(_T0), skills, ROLE_CATALOG)
            decision = decide_role(current=held.get(store.character), held_cycles=0,
                                   live_leases=store.live_leases(_T0),
                                   demand_by_role=by_role,
                                   character=store.character, catalog=ROLE_CATALOG)
            assert decision.claim is not None
            assert store.claim(decision.claim, _T0) is True
            held[store.character] = decision.claim

        assert held["HAL"] != held["C3P0"]
        assert hal.live_leases(_T0) == {held["HAL"]: frozenset({"HAL"}),
                                        held["C3P0"]: frozenset({"C3P0"})}
    finally:
        hal.close()
        c3po.close()


# ---------------------------------------------------------------------------
# GameData.producing_skill — the item -> producing-skill lookup
# `_update_coordination` feeds `demand_by_role`. Composes the unified
# RequirementGraph's `craft_skill` / `gather_skill` maps rather than
# re-deriving them.
# ---------------------------------------------------------------------------

def _skill_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "iron_bar": ItemStats(code="iron_bar", level=10, type_="resource",
                              crafting_skill="mining", crafting_level=10),
    }
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10},
                            "iron_bar": {"iron_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore", "iron_rocks": "iron_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1), "iron_rocks": ("mining", 10)}
    return gd


def test_producing_skill_prefers_the_craft_skill_when_craftable():
    assert _skill_gd().producing_skill("copper_bar") == "mining"


def test_producing_skill_falls_back_to_the_gathering_skill():
    # copper_ore has no ItemStats/crafting_skill entry, so it falls through
    # to the gather-skill map built from resource_drops/resource_skill.
    assert _skill_gd().producing_skill("copper_ore") == "mining"


def test_producing_skill_none_when_the_api_exposes_neither():
    assert _skill_gd().producing_skill("no_such_item") is None


def test_producing_requirement_reads_a_craftables_level_off_the_recipe():
    """A CRAFTED item's requirement is `item.craft.level` off /v3/items,
    carried through `ItemStats.crafting_level` onto `RequirementGraph`."""
    assert _skill_gd().producing_requirement("iron_bar") == ("mining", 10)


def test_producing_requirement_reads_a_gathered_items_level_off_the_resource():
    """A GATHERED item's requirement is the resource NODE's level off
    /v3/resources — a different table entirely — resolved from resource-keyed
    to item-keyed by `_gather_skill_by_item`. `iron_ore` has no craft entry,
    so its 10 comes from `iron_rocks`, not from any item field."""
    assert _skill_gd().producing_requirement("iron_ore") == ("mining", 10)
    assert _skill_gd().producing_requirement("copper_ore") == ("mining", 1)


def test_producing_requirement_none_when_the_api_exposes_neither():
    assert _skill_gd().producing_requirement("no_such_item") is None


# ---------------------------------------------------------------------------
# GamePlayer._own_unmet_demand
# ---------------------------------------------------------------------------

def test_own_unmet_demand_empty_without_a_crafting_target():
    p = GamePlayer(character="hero")
    assert p._last_decide_crafting_target is None
    assert p._own_unmet_demand(make_state(), _make_planner_gd()) == {}


def test_own_unmet_demand_subtracts_held_inventory():
    p = GamePlayer(character="hero")
    gd = _make_planner_gd()
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 2}}
    p._last_decide_crafting_target = "copper_dagger"
    state = make_state(inventory={"copper_bar": 1})
    assert p._own_unmet_demand(state, gd) == {"copper_dagger": 1, "copper_bar": 1}


def test_own_unmet_demand_excludes_fully_held_items():
    p = GamePlayer(character="hero")
    gd = _make_planner_gd()
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 2}}
    p._last_decide_crafting_target = "copper_dagger"
    state = make_state(inventory={"copper_bar": 2, "copper_dagger": 1})
    assert p._own_unmet_demand(state, gd) == {}


def test_own_unmet_demand_nets_the_account_wide_bank_too():
    """The bank is ACCOUNT-WIDE (shared across every character), so material
    already banked — by this character in an earlier session, or by a
    sibling — already satisfies the demand and must not be re-published.
    Without this, a sibling's `_pick_supply_target` targets
    `banked + full_demand` on top of stock that already exists: systematic
    over-production of exactly what the fleet already holds."""
    p = GamePlayer(character="hero")
    gd = _make_planner_gd()
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 2}}
    p._last_decide_crafting_target = "copper_dagger"
    # Needs copper_bar x2; 1 in inventory, 1 already banked -> fully covered.
    state = make_state(inventory={"copper_bar": 1}, bank_items={"copper_bar": 1})
    assert p._own_unmet_demand(state, gd) == {"copper_dagger": 1}


def test_own_unmet_demand_bank_netting_only_partially_covers():
    p = GamePlayer(character="hero")
    gd = _make_planner_gd()
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 5}}
    p._last_decide_crafting_target = "copper_dagger"
    state = make_state(inventory={}, bank_items={"copper_bar": 2})
    assert p._own_unmet_demand(state, gd) == {"copper_dagger": 1, "copper_bar": 3}


# ---------------------------------------------------------------------------
# GamePlayer._pick_supply_target
# ---------------------------------------------------------------------------

def test_pick_supply_target_none_without_a_held_role():
    p = GamePlayer(character="hero")
    assert p._role is None
    result = p._pick_supply_target({"copper_ore": 5}, {"copper_ore": "mining"},
                                   make_state(), {})
    assert result is None


def test_pick_supply_target_none_for_an_unknown_role():
    p = GamePlayer(character="hero")
    p._role = "not_a_real_role"
    result = p._pick_supply_target({"copper_ore": 5}, {"copper_ore": "mining"},
                                   make_state(), {})
    assert result is None


def test_pick_supply_target_ignores_demand_outside_the_role_skills():
    p = GamePlayer(character="hero")
    p._role = "miner"  # owns {mining, weaponcrafting}
    item_demand = {"ash_plank": 9}  # woodcutting/gearcrafting -> logger's territory
    skill_of_item = {"ash_plank": "woodcutting"}
    # bank_items={}, NOT the `make_state()` default of "never visited": with the
    # default this returns None for the bank reason no matter what the skill
    # filter does, and the assertion pins nothing (a dropped ownership test
    # survived here).
    state = make_state(bank_items={})
    assert p._pick_supply_target(item_demand, skill_of_item, state, {}) is None


def test_pick_supply_target_ignores_demand_with_no_producing_skill_at_all():
    """`skill_of_item` carries None for an item the API exposes no producer
    for. It is not the role's, and it is not anybody's — skipped before the
    level gate is consulted, since there is no skill to read a level in."""
    p = GamePlayer(character="hero")
    p._role = "miner"
    assert p._pick_supply_target({"mystery": 9}, {"mystery": None},
                                 make_state(bank_items={}), {}) is None


def test_pick_supply_target_picks_the_highest_demand_match():
    p = GamePlayer(character="hero")
    p._role = "miner"
    item_demand = {"copper_ore": 4, "iron_ore": 9}
    skill_of_item = {"copper_ore": "mining", "iron_ore": "mining"}
    state = make_state(bank_items={"iron_ore": 1})
    assert p._pick_supply_target(item_demand, skill_of_item, state, {}) == ("iron_ore", 10, 9)


def test_pick_supply_target_skips_an_item_this_character_cannot_produce():
    """The gate `demand_by_role` applies, applied to the ITEM choice as well.
    A `miner` at mining 8 recruited by copper demand must target the copper it
    can gather, not the higher-demand iron it cannot — otherwise the role is
    served by a goal that can never plan, and the fix would only have moved the
    stall from role selection to supply selection."""
    p = GamePlayer(character="hero")
    p._role = "miner"
    item_demand = {"copper_ore": 4, "iron_ore": 9}
    skill_of_item = {"copper_ore": "mining", "iron_ore": "mining"}
    level_of_item = {"copper_ore": 1, "iron_ore": 10}
    state = make_state(bank_items={}, skills=dict(_LOR_SKILLS))
    assert p._pick_supply_target(item_demand, skill_of_item, state,
                                 level_of_item) == ("copper_ore", 4, 4)


def test_pick_supply_target_keeps_an_item_the_character_can_produce():
    """The other side of the same gate: at mining 21 the iron is servable and
    remains the highest-demand target. Pins that the gate is a level
    comparison, not a blanket skip of anything carrying a requirement."""
    p = GamePlayer(character="hero")
    p._role = "miner"
    item_demand = {"copper_ore": 4, "iron_ore": 9}
    skill_of_item = {"copper_ore": "mining", "iron_ore": "mining"}
    level_of_item = {"copper_ore": 1, "iron_ore": 10}
    state = make_state(bank_items={}, skills=dict(_ROBBY_SKILLS))
    assert p._pick_supply_target(item_demand, skill_of_item, state,
                                 level_of_item) == ("iron_ore", 9, 9)


def test_pick_supply_target_none_when_the_bank_has_never_been_visited():
    """`bank_items is None` means "never visited this session" (see its field
    docstring in `world_state.py`), NOT "empty" — the same distinction
    `bank_room.bank_has_room` draws for the same field. Fabricating
    `banked=0` here would understate the eventual target once the real
    contents are known, so this must return None rather than guess."""
    p = GamePlayer(character="hero")
    p._role = "miner"
    item_demand = {"copper_ore": 3}
    skill_of_item = {"copper_ore": "mining"}
    state = make_state(bank_items=None)
    assert p._pick_supply_target(item_demand, skill_of_item, state, {}) is None


def test_pick_supply_target_treats_a_visited_empty_bank_as_zero():
    """Once the bank HAS been visited (even if genuinely empty, `{}`), the
    absence of the item is real information — banked=0 is correct, not a
    guess — so a target IS computed. This is the case
    `test_pick_supply_target_none_when_the_bank_has_never_been_visited`
    must be distinguished from."""
    p = GamePlayer(character="hero")
    p._role = "miner"
    item_demand = {"copper_ore": 3}
    skill_of_item = {"copper_ore": "mining"}
    state = make_state(bank_items={})
    assert p._pick_supply_target(item_demand, skill_of_item, state, {}) == ("copper_ore", 3, 3)


# ---------------------------------------------------------------------------
# GamePlayer._update_coordination — the full per-cycle seam
# ---------------------------------------------------------------------------

def test_update_coordination_is_a_noop_without_a_store():
    """The single-character path: no store attached, nothing changes. This is
    the bit-identical guarantee — `run()` calls `_update_coordination`
    unconditionally, so this is the ONLY thing standing between a lone
    `play <character>` and a behavior change."""
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    p._supply_target = ("stale", 1, 1)  # prove it gets CLEARED, not left stale
    p._update_coordination(p.state, p.game_data)
    assert p._coordination is None
    assert p._supply_target is None
    assert p._role is None
    assert p._role_held_cycles == 0
    ctx = p._selection_context(combat_monster=None)
    assert ctx.supply_target is None


def test_set_coordination_store_attaches_it():
    p = GamePlayer(character="hero")
    assert p._coordination is None
    store = CoordinationStore(db_path=":memory:", character="hero")
    try:
        p.set_coordination_store(store)
        assert p._coordination is store
    finally:
        store.close()


def test_update_coordination_claims_a_role_when_none_held(tmp_path):
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="hero")
    p.set_coordination_store(store)
    try:
        p._update_coordination(p.state, p.game_data)
        assert p._role in {r.name for r in ROLE_CATALOG}
        assert p._role_held_cycles == 0
        assert store.live_leases(datetime.now(tz=timezone.utc))[p._role] == frozenset({"hero"})
    finally:
        store.close()


def test_update_coordination_joins_a_role_two_siblings_already_hold(tmp_path):
    """End to end through the real store: the third character on one role.

    `make_state` gives hero mining 3 as its best skill, so `miner` is its
    top-affinity role, and two siblings already hold it. Under exclusivity the
    lease would have been unavailable and hero would have cascaded to its
    second choice — the precise mechanism that put the account's best miner on
    alchemy. Hero must now simply join, and the lease table must name all
    three."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    store = CoordinationStore(db_path=db, character="hero")
    siblings = [CoordinationStore(db_path=db, character=n) for n in ("HAL", "C3P0")]
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        for sibling in siblings:
            assert sibling.claim("miner", now) is True

        p._update_coordination(p.state, p.game_data)

        assert p._role == "miner"
        assert store.live_leases(datetime.now(tz=timezone.utc))["miner"] == frozenset(
            {"hero", "HAL", "C3P0"})
    finally:
        store.close()
        for sibling in siblings:
            sibling.close()


def test_update_coordination_keeps_and_increments_held_cycles(tmp_path):
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="hero")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = 5
        p._update_coordination(p.state, p.game_data)
        assert p._role == "miner"
        assert p._role_held_cycles == 6
    finally:
        store.close()


def test_update_coordination_does_not_set_role_when_the_claim_does_not_land(tmp_path, monkeypatch):
    """`CoordinationStore.claim` can still return False — no longer because a
    sibling won a race (roles are not exclusive, so there is no race to lose)
    but because the DB write itself failed. `_update_coordination` must not
    commit to a role that has no lease row: it would supply for a role no
    sibling's holder count includes, so the role's demand is never divided by
    this character and a sibling joins work already being done."""
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="hero")
    p.set_coordination_store(store)
    monkeypatch.setattr(store, "claim", lambda role, now: False)
    try:
        p._update_coordination(p.state, p.game_data)
        assert p._role is None
        assert p._role_held_cycles == 0
    finally:
        store.close()


def test_update_coordination_clears_a_stale_role_when_a_reclaim_does_not_land(tmp_path, monkeypatch):
    """The critical defect, on the re-claim path rather than the cold-start
    one: `decide_role` returns `claim=current` when THIS character is absent
    from `live_leases[current]` — its own lease lapsed during a stall. (A
    sibling can no longer take the role away; its claim writes its own row.)
    If that re-claim does not land, `self._role` must be cleared, not left
    stale: leaving it set makes the character renew a lease that does not
    exist (a no-op) and keep computing `_supply_target` for a role it is not
    on the board for — every cycle, forever, since the same failing re-claim
    repeats identically next cycle."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        # hero's lease on "miner" lapsed and rival took it over. hero's
        # in-memory `_role` is stale (still says "miner").
        sibling.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = 5
        monkeypatch.setattr(store, "claim", lambda role, now: False)
        p._update_coordination(p.state, p.game_data)
        assert p._role is None
        assert p._role_held_cycles == 0
    finally:
        store.close()
        sibling.close()


def test_update_coordination_renews_the_lease_only_while_a_role_is_held(tmp_path, monkeypatch):
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="hero")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    renewed: list[str] = []
    monkeypatch.setattr(store, "renew", lambda role, now: renewed.append(role))
    try:
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = 5
        p._update_coordination(p.state, p.game_data)
        assert renewed == ["miner"]

        renewed.clear()
        p._role = None
        p._update_coordination(p.state, p.game_data)
        assert renewed == []
    finally:
        store.close()


def test_update_coordination_releases_an_idle_role_after_min_hold(tmp_path):
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(bank_items={})
    p.game_data = _two_role_demand_gd()
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        # Somewhere to go: `logger` wants work, `miner` (hero's role) does not.
        sibling.publish_demand({"ash_wood": 5}, frozenset(), now)
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = ROLE_MIN_HOLD_CYCLES  # eligible; own demand is 0
        # One short of the dwell window: `_update_coordination` extends the run
        # to exactly ROLE_IDLE_DWELL_CYCLES before it decides.
        p._role_zero_demand_cycles = ROLE_IDLE_DWELL_CYCLES - 1
        p._update_coordination(p.state, p.game_data)
        assert "miner" in p._role_idle_released
        assert p._role_held_cycles == 0
    finally:
        store.close()
        sibling.close()


def test_update_coordination_keeps_an_idle_role_when_nothing_else_wants_work(tmp_path):
    """RESIDUAL 2 through the real caller. Same setup as the test above with
    the sibling's request withdrawn: with the whole board silent there is
    nowhere better to go, so the release would buy nothing and cost a lease
    write, a claim and another dwell — repeated once per role until the catalog
    ran out."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(bank_items={})
    p.game_data = _two_role_demand_gd()
    store = CoordinationStore(db_path=db, character="hero")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = ROLE_MIN_HOLD_CYCLES
        p._role_zero_demand_cycles = ROLE_IDLE_DWELL_CYCLES - 1
        p._update_coordination(p.state, p.game_data)
        assert p._role == "miner"
        assert p._role_idle_released == frozenset()
        assert store.live_leases(now).get("miner") == frozenset({"hero"})
    finally:
        store.close()


def test_update_coordination_idle_release_does_not_immediately_reclaim(tmp_path):
    """The churn hole Task 6's `idle_released` ruling closes, through the real
    caller.

    `miner` is hero's top-affinity role (`make_state` gives mining 3, its best
    skill), and the whole board is silent, so the claim ranks on affinity alone
    — a fixed property of the character. Releasing `miner` as idle and then
    re-deciding must NOT hand it straight back, or the loop is infinite.

    Non-exclusivity made this MORE reachable, not less. The original version of
    this test had to lease every OTHER role to a sibling to corner hero on
    `miner`; now no role is ever unavailable, and hero still re-picks `miner`
    every cycle for the reason that actually drives it — it is what hero is
    best at. Hero does move on to some other role here (nothing is idle-blocked
    yet but `miner`), and that is fine: what must never happen is going back."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(bank_items={})
    p.game_data = _two_role_demand_gd()
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        # `logger` wants work, which is what makes the idle release fire at all.
        sibling.publish_demand({"ash_wood": 5}, frozenset(), now)
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = ROLE_MIN_HOLD_CYCLES
        p._role_zero_demand_cycles = ROLE_IDLE_DWELL_CYCLES - 1

        p._update_coordination(p.state, p.game_data)
        assert p._role is None  # released: own demand is zero
        assert "miner" in p._role_idle_released

        # Re-decide immediately: `miner` still scores highest on affinity and
        # still has zero demand. Without idle_released this reclaims it.
        p._update_coordination(p.state, p.game_data)
        assert p._role != "miner"
        assert "miner" not in store.live_leases(datetime.now(tz=timezone.utc))
    finally:
        store.close()
        sibling.close()


def _mining_demand_gd() -> GameData:
    """A catalog where `copper_ore` routes to the miner role, so a sibling's
    published demand actually lands on the role hero holds."""
    gd = _make_planner_gd()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    return gd


def _two_role_demand_gd() -> GameData:
    """`_mining_demand_gd` plus a woodcutting resource, so a sibling can put
    demand on a role hero does NOT hold.

    Release-on-idle now requires a DESTINATION — some claimable role carrying
    positive demand — because freeing a finished role no longer helps a sibling
    (nothing is exclusive) and the only thing a release still buys is moving
    this character somewhere useful. A catalog that can only express miner
    demand cannot express that destination."""
    gd = _mining_demand_gd()
    gd._resource_drops = {"copper_rocks": "copper_ore", "ash_tree": "ash_wood"}
    gd._resource_skill = {"copper_rocks": ("mining", 1), "ash_tree": ("woodcutting", 1)}
    return gd


def test_update_coordination_extends_the_zero_demand_run(tmp_path):
    """The counter `decide_role`'s dwell rule consumes is the caller's, and it
    has to grow one per consecutive quiet cycle."""
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _mining_demand_gd()
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="hero")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        store.claim("miner", now)
        p._role = "miner"
        p._update_coordination(p.state, p.game_data)
        p._update_coordination(p.state, p.game_data)
        assert p._role_zero_demand_cycles == 2
    finally:
        store.close()


def test_update_coordination_breaks_the_zero_demand_run_on_real_demand(tmp_path):
    """One cycle of genuine demand resets the run to zero — the whole point of
    requiring CONSECUTIVE observations."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(bank_items={})
    p.game_data = _mining_demand_gd()
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        store.claim("miner", now)
        p._role = "miner"
        p._role_zero_demand_cycles = ROLE_IDLE_DWELL_CYCLES - 2
        sibling.publish_demand({"copper_ore": 5}, frozenset(), now)
        p._update_coordination(p.state, p.game_data)
        assert p._role_zero_demand_cycles == 0
    finally:
        store.close()
        sibling.close()


def test_update_coordination_clears_the_zero_demand_run_while_holding_no_role(tmp_path):
    """The run is about a HELD role, so a character holding none carries no
    run into the role it claims this cycle."""
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _mining_demand_gd()
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="hero")
    p.set_coordination_store(store)
    try:
        p._role_zero_demand_cycles = ROLE_IDLE_DWELL_CYCLES
        p._update_coordination(p.state, p.game_data)  # holds none -> claims
        assert p._role is not None
        assert p._role_zero_demand_cycles == 0
    finally:
        store.close()


def test_update_coordination_computes_the_supply_target_from_sibling_demand(tmp_path):
    db = str(tmp_path / "coord.db")
    gd = _make_planner_gd()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    p = GamePlayer(character="hero")
    p.state = make_state(bank_items={"copper_ore": 2})
    p.game_data = gd
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        sibling.publish_demand({"copper_ore": 5}, frozenset(), now)
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = 3  # below ROLE_MIN_HOLD_CYCLES: stays "miner" (keep)
        p._update_coordination(p.state, p.game_data)
        assert p._role == "miner"
        assert p._supply_target == ("copper_ore", 7, 5)  # banked(2) + demand(5)
        ctx = p._selection_context(combat_monster=None)
        assert ctx.supply_target == ("copper_ore", 7, 5)
    finally:
        store.close()
        sibling.close()


def test_update_coordination_supply_target_none_without_a_matching_role(tmp_path):
    db = str(tmp_path / "coord.db")
    gd = _make_planner_gd()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = gd
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        sibling.publish_demand({"copper_ore": 5}, frozenset(), now)
        # hero holds "jeweler" (jewelrycrafting only) — cannot serve mining
        # demand, so no supply target even though sibling demand exists.
        store.claim("jeweler", now)
        p._role = "jeweler"
        p._role_held_cycles = 3
        p._update_coordination(p.state, p.game_data)
        assert p._role == "jeweler"
        assert p._supply_target is None
    finally:
        store.close()
        sibling.close()


# ---------------------------------------------------------------------------
# GamePlayer._note_supply_servability — the caller-owned evidence behind
# `decide_role`'s release-on-unservable rule. The signal is the ARBITER's own
# verdict, read out of `goals_tried`, which is a search it already performed:
# neither `_pick_supply_target() is None` nor `SupplyBankGoal.is_plannable()`
# can see the Lor failure (measured against the committed gamedata bundle —
# is_plannable is True for every alchemy target at alchemy level 1, while the
# real search for SupplyBank(health_potionx10) returns no plan).
# ---------------------------------------------------------------------------

def _tried(target, plan_len: int) -> list[dict[str, object]]:
    """The arbiter record for the supply goal built from `target`."""
    goal = SupplyBankGoal(item_code=target[0], quantity=target[1], demand=target[2])
    return [{"goal": "GrindCharacterXP", "plan_len": 3},
            {"goal": repr(goal), "plan_len": plan_len}]


def test_note_supply_servability_extends_the_run_when_the_goal_finds_no_plan():
    p = GamePlayer(character="hero")
    p._supply_target = ("copper_ore", 7, 5)
    p._note_supply_servability(_tried(p._supply_target, 0))
    p._note_supply_servability(_tried(p._supply_target, 0))
    assert p._role_unservable_cycles == 2


def test_note_supply_servability_breaks_the_run_on_a_real_plan():
    p = GamePlayer(character="hero")
    p._supply_target = ("copper_ore", 7, 5)
    p._role_unservable_cycles = ROLE_UNSERVABLE_CYCLES - 1
    p._note_supply_servability(_tried(p._supply_target, 4))
    assert p._role_unservable_cycles == 0


def test_note_supply_servability_leaves_the_run_alone_when_the_goal_was_not_tried():
    """Absence of evidence. A guard preempted selection, or the cached plan was
    reused (`goals_tried` is empty on a cache hit), or the demand is below
    `SUPPLY_DEMAND_MIN` so the means never fired — none of those is a statement
    about whether this character CAN serve the role, so neither extending nor
    clearing the run would be honest."""
    p = GamePlayer(character="hero")
    p._supply_target = ("copper_ore", 7, 5)
    p._role_unservable_cycles = 4
    p._note_supply_servability([])
    p._note_supply_servability([{"goal": "GrindCharacterXP", "plan_len": 0}])
    assert p._role_unservable_cycles == 4


def test_note_supply_servability_clears_the_run_without_a_supply_target():
    """Same scoping the zero-demand counter uses: the run is about a role we
    are actively supplying, so no target (no role held, or nothing the role
    produces is in demand) means no run."""
    p = GamePlayer(character="hero")
    p._role_unservable_cycles = 9
    assert p._supply_target is None
    p._note_supply_servability(_tried(("copper_ore", 7, 5), 0))
    assert p._role_unservable_cycles == 0


# ---------------------------------------------------------------------------
# GamePlayer._update_coordination — the unservable release, end to end
# ---------------------------------------------------------------------------

def _held_miner(tmp_path, skills=None):
    """hero holding `miner` with a sibling asking for copper_ore, plus the two
    stores to close."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(bank_items={}, **({"skills": skills} if skills else {}))
    p.game_data = _mining_demand_gd()
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    sibling.publish_demand({"copper_ore": 5}, frozenset(), now)
    store.claim("miner", now)
    p._role = "miner"
    p._role_held_cycles = ROLE_MIN_HOLD_CYCLES
    return p, store, sibling


def test_update_coordination_releases_a_role_it_cannot_serve(tmp_path):
    """GAP A, the Lor scenario through the real seam: demand is POSITIVE (so
    release-on-idle cannot fire) and has gone unserved for a full run."""
    p, store, sibling = _held_miner(tmp_path)
    try:
        p._role_unservable_cycles = ROLE_UNSERVABLE_CYCLES
        p._update_coordination(p.state, p.game_data)
        assert p._role != "miner"
        # Blocked at the skill level the verdict was reached at: miner owns
        # {mining, weaponcrafting} and the fixture character has mining 3.
        assert p._role_unservable_released == {"miner": 3}
        assert store.live_leases(datetime.now(tz=timezone.utc)).get("miner") is None
    finally:
        store.close()
        sibling.close()


def test_update_coordination_keeps_a_role_it_is_still_serving(tmp_path):
    """The other side of the same conditional: an unfinished run holds."""
    p, store, sibling = _held_miner(tmp_path)
    try:
        p._role_unservable_cycles = ROLE_UNSERVABLE_CYCLES - 1
        p._update_coordination(p.state, p.game_data)
        assert p._role == "miner"
        assert p._role_unservable_released == {}
    finally:
        store.close()
        sibling.close()


def test_update_coordination_does_not_block_an_idle_release(tmp_path):
    """Only an UNSERVABLE release blocks the re-claim. A role released because
    nothing needed it any more is a different verdict — it must stay
    re-claimable the instant demand returns, which is what `_role_idle_released`
    (conditional on non-positive demand) already provides."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(bank_items={})
    p.game_data = _two_role_demand_gd()
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        sibling.publish_demand({"ash_wood": 5}, frozenset(), now)
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = ROLE_MIN_HOLD_CYCLES
        p._role_zero_demand_cycles = ROLE_IDLE_DWELL_CYCLES - 1
        p._update_coordination(p.state, p.game_data)
        assert "miner" in p._role_idle_released
        assert p._role_unservable_released == {}
    finally:
        store.close()
        sibling.close()


def test_update_coordination_does_not_reclaim_an_unservable_role(tmp_path):
    """The churn hole unique to this release: the demand that triggered it is
    POSITIVE, so `_role_idle_released` (which only holds a role back while its
    demand is non-positive) would hand it straight back next cycle."""
    p, store, sibling = _held_miner(tmp_path)
    try:
        p._role_unservable_cycles = ROLE_UNSERVABLE_CYCLES
        p._update_coordination(p.state, p.game_data)
        assert "miner" in p._role_unservable_released
        for _ in range(3):
            p._update_coordination(p.state, p.game_data)
            assert p._role != "miner"
    finally:
        store.close()
        sibling.close()


def test_update_coordination_reopens_an_unservable_role_once_the_skill_rises(tmp_path):
    """...and it becomes claimable again the moment the verdict could have
    changed. Skill progress is the only thing that can change "I cannot serve
    this", and the role is free on the shared board the whole time, so a
    better-suited sibling never waits on this."""
    p, store, sibling = _held_miner(tmp_path)
    try:
        p._role_unservable_cycles = ROLE_UNSERVABLE_CYCLES
        p._update_coordination(p.state, p.game_data)
        assert "miner" in p._role_unservable_released

        # Same level: still blocked.
        p._update_coordination(p.state, p.game_data)
        assert "miner" in p._role_unservable_released

        # Mining 3 -> 4: the block lifts.
        skills = dict(p.state.skills)
        skills["mining"] = skills["mining"] + 1
        p.state = make_state(bank_items={}, skills=skills)
        p._role = None
        p._role_held_cycles = 0
        p._update_coordination(p.state, p.game_data)
        assert "miner" not in p._role_unservable_released
    finally:
        store.close()
        sibling.close()


def test_update_coordination_claims_the_role_its_skills_fit(tmp_path):
    """GAP B through the real seam: `state.skills` reaches `decide_role`, so a
    trained jewelrycrafter claims `jeweler` where the demand-only ranking gave
    everyone the first catalog entry. Proves the parameter is not inert."""
    p = GamePlayer(character="hero")
    p.game_data = _mining_demand_gd()
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="hero")
    p.set_coordination_store(store)
    try:
        flat = {s: 1 for s in make_state().skills}
        p.state = make_state(skills=flat)
        p._update_coordination(p.state, p.game_data)
        assert p._role == ROLE_CATALOG[0].name  # no fit signal -> catalog order

        p._role, p._role_held_cycles = None, 0
        store.release(ROLE_CATALOG[0].name)
        p.state = make_state(skills={**flat, "jewelrycrafting": 20})
        p._update_coordination(p.state, p.game_data)
        assert p._role == "jeweler"
    finally:
        store.close()


def _iron_gated_gd() -> GameData:
    """`iron_rocks` gates at mining 10, `ash_tree` at woodcutting 1 — the two
    real gates behind the 2026-08-03 misallocation, in the smallest catalog
    that can express it."""
    gd = _make_planner_gd()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_drops = {"iron_rocks": "iron_ore", "ash_tree": "ash_wood"}
    gd._resource_skill = {"iron_rocks": ("mining", 10), "ash_tree": ("woodcutting", 1)}
    return gd


def _decide_with_skills(tmp_path, name, skills) -> str | None:
    """One full `_update_coordination` for a cold-start character with `skills`,
    against a sibling publishing iron-dominated demand."""
    db = str(tmp_path / f"coord_{name}.db")
    p = GamePlayer(character=name)
    p.state = make_state(bank_items={}, skills=skills)
    p.game_data = _iron_gated_gd()
    store = CoordinationStore(db_path=db, character=name)
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    try:
        sibling.publish_demand({"iron_ore": 30, "ash_wood": 6}, frozenset(),
                               datetime.now(tz=timezone.utc))
        p._update_coordination(p.state, p.game_data)
        return p._role
    finally:
        store.close()
        sibling.close()


def test_update_coordination_does_not_recruit_a_character_below_the_item_gate(tmp_path):
    """THE OBSERVED CASE through the real seam, level requirement and all.

    Iron dominates the board 30:6, and `Lor`'s mining 8 is its best skill
    anywhere, so both demand and self-relative affinity pointed at `miner` —
    which it then held, unable to gather or craft a single unit, until
    release-on-unservable would have taken 25 wasted cycles to notice. The
    requirement is in the item catalog and the level is on the character, so
    the gate is decided before the first planner search instead."""
    assert _decide_with_skills(tmp_path, "Lor", dict(_LOR_SKILLS)) == "logger"


def test_update_coordination_still_recruits_a_character_above_the_item_gate(tmp_path):
    """Same board, same catalog, mining 21: the iron IS servable, so it counts
    and `miner` wins on it. The gate reads levels, it does not mute mining."""
    assert _decide_with_skills(tmp_path, "Robby", dict(_ROBBY_SKILLS)) == "miner"


def test_update_coordination_supply_target_respects_the_same_gate(tmp_path):
    """The level gate reaches `_supply_target` too, not just the role. A miner
    at mining 8 holding `miner` must be pointed at the copper it can gather,
    never at the higher-demand iron it cannot — the two readers of
    `serves_item` seeing the same board."""
    db = str(tmp_path / "coord.db")
    gd = _iron_gated_gd()
    gd._resource_drops = {**gd._resource_drops, "copper_rocks": "copper_ore"}
    gd._resource_skill = {**gd._resource_skill, "copper_rocks": ("mining", 1)}
    p = GamePlayer(character="Lor")
    p.state = make_state(bank_items={}, skills=dict(_LOR_SKILLS))
    p.game_data = gd
    store = CoordinationStore(db_path=db, character="Lor")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        sibling.publish_demand({"iron_ore": 30, "copper_ore": 4}, frozenset(), now)
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = 3  # below ROLE_MIN_HOLD_CYCLES: stays "miner"
        p._update_coordination(p.state, p.game_data)
        assert p._role == "miner"
        assert p._supply_target == ("copper_ore", 4, 4)
    finally:
        store.close()
        sibling.close()


# ---------------------------------------------------------------------------
# CycleSnapshot wiring: `_notify_observer` is the real construction site.
# ---------------------------------------------------------------------------

def test_notify_observer_populates_role_and_supply_target():
    calls: list[CycleSnapshot] = []
    player = GamePlayer(character="hero", cycle_observer=calls.append)
    player.state = make_state()
    player._role = "miner"
    player._supply_target = ("copper_ore", 10, 4)
    player._notify_observer("SupplyBank(copper_orex10)", "Gather(copper_rocks)", "ok",
                            goal_rank_trace=[])
    assert len(calls) == 1
    snap = calls[0]
    assert snap.role == "miner"
    assert snap.supply_target == repr(("copper_ore", 10, 4))


def test_notify_observer_role_and_supply_target_none_by_default():
    calls: list[CycleSnapshot] = []
    player = GamePlayer(character="hero", cycle_observer=calls.append)
    player.state = make_state()
    player._notify_observer("X", "Y", "ok", goal_rank_trace=[])
    assert len(calls) == 1
    snap = calls[0]
    assert snap.role is None
    assert snap.supply_target is None
    assert snap.role_change is None


def test_notify_observer_carries_this_cycles_role_change():
    """The log pane renders the transition as an event, and it can only do that
    from a snapshot field: `build_log_lines` is pure over ONE snapshot, and the
    widget cannot diff its way there because `replace_history` replays a
    bounded buffer whose earlier cycles may be gone."""
    calls: list[CycleSnapshot] = []
    player = GamePlayer(character="hero", cycle_observer=calls.append)
    player.state = make_state()
    player._role = "miner"
    player._role_change = RoleChange(previous=None, current="miner",
                                     reason="demand 12")
    player._notify_observer("X", "Y", "ok", goal_rank_trace=[])
    change = calls[0].role_change
    assert change is not None
    assert (change.previous, change.current, change.reason) == (None, "miner", "demand 12")


# ---------------------------------------------------------------------------
# GamePlayer._update_coordination — detecting the transition at the SOURCE
# ---------------------------------------------------------------------------

def test_update_coordination_records_a_claim_as_a_transition(tmp_path):
    p = GamePlayer(character="hero")
    p.state = make_state(bank_items={})
    p.game_data = _mining_demand_gd()
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="hero")
    p.set_coordination_store(store)
    try:
        p._update_coordination(p.state, p.game_data)
        assert p._role is not None
        change = p._role_change
        assert change is not None
        assert (change.previous, change.current) == (None, p._role)
        # The reason comes from the rule that fired, not from a second
        # derivation here — an empty board claims on affinity at demand 0.
        assert change.reason == "demand 0"
    finally:
        store.close()


def test_update_coordination_records_a_release_as_a_transition(tmp_path):
    p, store, sibling = _held_miner(tmp_path)
    try:
        p._role_unservable_cycles = ROLE_UNSERVABLE_CYCLES
        p._update_coordination(p.state, p.game_data)
        change = p._role_change
        assert change is not None
        assert (change.previous, change.current) == ("miner", None)
        assert change.reason == f"demand 5 unserved for {ROLE_UNSERVABLE_CYCLES} cycles"
    finally:
        store.close()
        sibling.close()


def test_update_coordination_records_no_transition_when_the_role_is_kept(tmp_path):
    """The quiet case, and the one the log's silence depends on: holding a role
    is not an event."""
    p, store, sibling = _held_miner(tmp_path)
    try:
        p._role_change = RoleChange(previous=None, current="miner")  # prove it CLEARS
        p._update_coordination(p.state, p.game_data)
        assert p._role == "miner"
        assert p._role_change is None
    finally:
        store.close()
        sibling.close()


def test_update_coordination_does_not_log_a_lapsed_lease_reclaim(tmp_path):
    """`decide_role` answers a lapsed lease with `claim=<the same role>`. The
    character never stopped holding it as far as the operator is concerned, so
    re-taking the row is not a role CHANGE — comparing the role before and
    after gets this right for free, where a per-branch 'this branch changed the
    role' flag would have logged a transition from miner to miner."""
    p, store, sibling = _held_miner(tmp_path)
    try:
        store.release("miner")               # the lease lapses under us
        p._update_coordination(p.state, p.game_data)
        assert p._role == "miner"            # re-claimed
        assert p._role_change is None
    finally:
        store.close()
        sibling.close()


def test_update_coordination_clears_the_role_change_without_a_store():
    """Every single-character run takes this path on every cycle."""
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _mining_demand_gd()
    p._role_change = RoleChange(previous=None, current="miner")
    p._update_coordination(p.state, p.game_data)
    assert p._role_change is None


# ---------------------------------------------------------------------------
# End-to-end: a coordinated SelectionContext must reach a real SupplyBankGoal
# through the arbiter's actual dispatch (`active_means`/`map_means` — the
# same two functions `StrategyArbiter.select` calls internally). Tasks 9/10
# already unit-test `_fires`/`map_means` against a HAND-BUILT ctx; this test
# is the missing link proving the player's REAL `_update_coordination` output
# is what those two functions see — the feature is not inert.
# ---------------------------------------------------------------------------

def test_a_coordinated_supply_target_reaches_a_real_supply_bank_goal(tmp_path):
    db = str(tmp_path / "coord.db")
    gd = _make_planner_gd()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    p = GamePlayer(character="hero")
    p.state = make_state(bank_items={"copper_ore": 2})
    p.game_data = gd
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        sibling.publish_demand({"copper_ore": SUPPLY_DEMAND_MIN + 2}, frozenset(), now)
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = 3  # below ROLE_MIN_HOLD_CYCLES: stays "miner"

        p._update_coordination(p.state, p.game_data)
        ctx = p._selection_context(combat_monster=None)
        # The quantity is now the Task 2 batch milestone (`SUPPLY_BATCH`), not
        # `banked + demand`: banked(2) + demand(SUPPLY_DEMAND_MIN + 2) crosses
        # the first batch boundary. The demand element is still reported
        # unchanged.
        assert ctx.supply_target == ("copper_ore",
                                     supply_batch_target_pure(2, SUPPLY_DEMAND_MIN + 2),
                                     SUPPLY_DEMAND_MIN + 2)

        # The last two links: _fires (the means predicate) and map_means (the
        # goal factory) — exactly what StrategyArbiter.select calls.
        assert _fires(MeansKind.SUPPLY_BANK, p.state, gd, None, ctx) is True
        goal = map_means(MeansKind.SUPPLY_BANK, gd, ctx, p.state)
        assert isinstance(goal, SupplyBankGoal)
        assert goal._item_code == "copper_ore"
        assert goal._quantity == supply_batch_target_pure(2, SUPPLY_DEMAND_MIN + 2)
        assert goal._demand == SUPPLY_DEMAND_MIN + 2
        assert repr(goal) == f"SupplyBank(copper_orex{supply_batch_target_pure(2, SUPPLY_DEMAND_MIN + 2)})"
    finally:
        store.close()
        sibling.close()


def test_a_sub_threshold_coordinated_demand_is_targeted_but_never_fires(tmp_path):
    """End-to-end read-back of the 2026-08-01 gate: coordination still computes
    a supply target for a small sibling request (the board is unchanged), but
    `_fires` declines it, so the character keeps working its own objective
    instead of pausing for a handful of units the sibling can gather itself.

    `self_servable={"copper_ore"}` on the publish is the point of this fixture
    (Task 4): the sibling CAN mine copper_ore itself, so this demand is
    symmetric and must NOT trip the asymmetry arm `_fires` added — only the
    bulk-threshold arm applies here, and it declines a sub-threshold request."""
    db = str(tmp_path / "coord.db")
    gd = _make_planner_gd()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    p = GamePlayer(character="hero")
    p.state = make_state(bank_items={"copper_ore": 2})
    p.game_data = gd
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        sibling.publish_demand({"copper_ore": SUPPLY_DEMAND_MIN - 1},
                               frozenset({"copper_ore"}), now)
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = 3

        p._update_coordination(p.state, p.game_data)
        ctx = p._selection_context(combat_monster=None)
        # Same Task 2 batch-target substitution as the test above.
        assert ctx.supply_target == ("copper_ore",
                                     supply_batch_target_pure(2, SUPPLY_DEMAND_MIN - 1),
                                     SUPPLY_DEMAND_MIN - 1)
        assert _fires(MeansKind.SUPPLY_BANK, p.state, gd, None, ctx) is False
    finally:
        store.close()
        sibling.close()


# ---------------------------------------------------------------------------
# Bank-stock claims (2026-08-05). The bank is ACCOUNT-shared, so all five
# children hold the same `bank_items` and `bank_drain_excess` derives the same
# shed licence from it; the losers of that race pay HTTP 478 out of the per-IP
# request budget. The claim is WRITTEN at the general withdraw seam
# (`_execute`, any WithdrawItemAction) and READ only by the drain — see
# `ai/bank_drain`'s module docstring for why those two scopes differ.
#
# Coverage note: `branch = false`, so each conditional is pinned at BOTH
# outcomes — store/no store, withdraw/non-withdraw, success/structured
# failure/transport failure.
# ---------------------------------------------------------------------------

def _bank_sync_patches(bank_rows):
    """The four API reads `_execute` makes around a successful bank action:
    the post-action character refetch is skipped on success, but `_sync_bank`
    pages `/my/bank/items` and reads `/my/bank`. Real patches of the API
    surface, never of `GamePlayer` itself."""
    items = MagicMock()
    items.data = bank_rows
    details = MagicMock()
    details.data = MagicMock()
    details.data.gold = 0
    details.data.slots = 60
    return (patch("artifactsmmo_cli.ai.player.get_bank_items", return_value=items),
            patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=details))


def test_update_coordination_reads_sibling_bank_claims(tmp_path):
    """The read half, wired: what a sibling committed to withdrawing reaches
    `SelectionContext.sibling_bank_claims`, which is what `bank_drain_excess`
    nets against the shared bank snapshot."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(bank_items={"sap": 111})
    p.game_data = _make_planner_gd()
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    try:
        sibling.claim_bank_stock({"sap": 90}, datetime.now(tz=timezone.utc))
        p._update_coordination(p.state, p.game_data)
        assert p._sibling_bank_claims == {"sap": 90}
        assert p._selection_context(combat_monster=None).sibling_bank_claims == {"sap": 90}
    finally:
        store.close()
        sibling.close()


def test_update_coordination_clears_sibling_bank_claims_without_a_store():
    """The single-character path, and the bit-identical guarantee: with no
    store the claim map is EMPTY, not stale, so `bank_drain_excess` computes
    exactly what it computed before this feature existed."""
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    p._sibling_bank_claims = {"sap": 90}  # prove it gets CLEARED, not left stale
    p._update_coordination(p.state, p.game_data)
    assert p._coordination is None
    assert p._sibling_bank_claims == {}
    assert p._selection_context(combat_monster=None).sibling_bank_claims == {}


def test_a_character_never_reads_back_its_own_bank_claim(tmp_path):
    """Self-exclusion end to end: after committing to a withdraw, this
    character's own drain licence must NOT shrink — it would stop planning the
    very drain it is executing."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(bank_items={"sap": 111})
    p.game_data = _make_planner_gd()
    store = CoordinationStore(db_path=db, character="hero")
    p.set_coordination_store(store)
    try:
        store.claim_bank_stock({"sap": 90}, datetime.now(tz=timezone.utc))
        p._update_coordination(p.state, p.game_data)
        assert p._sibling_bank_claims == {}
    finally:
        store.close()


def test_claim_bank_stock_is_a_noop_without_a_store():
    p = GamePlayer(character="hero")
    p._claim_bank_stock(WithdrawItemAction(code="sap", quantity=5))  # must not raise


def test_release_bank_stock_is_a_noop_without_a_store():
    p = GamePlayer(character="hero")
    p._release_bank_stock(WithdrawItemAction(code="sap", quantity=5))  # must not raise


def test_release_bank_stock_leaves_a_claim_alone_for_a_non_withdraw_action(tmp_path):
    """`_release_bank_stock` is called from the failure branches for EVERY
    action, so it has to distinguish. A Move that 478s must not free the units
    an in-flight withdraw is holding."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    store = CoordinationStore(db_path=db, character="hero")
    observer = CoordinationStore(db_path=db, character="observer")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        store.claim_bank_stock({"sap": 22}, now)
        p._release_bank_stock(MoveAction(x=1, y=1))
        assert observer.sibling_bank_claims(now) == {"sap": 22}
        p._release_bank_stock(WithdrawItemAction(code="sap", quantity=22))
        assert observer.sibling_bank_claims(now) == {}
    finally:
        store.close()
        observer.close()


def test_execute_publishes_the_claim_before_the_withdraw_request(tmp_path):
    """ORDERING is the whole mechanism: a claim published after the request
    would be invisible to the sibling that is deriving its licence right now.
    The assertion runs INSIDE the patched API call, so it can only pass if the
    claim landed first."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(x=4, y=0, bank_items={"sap": 111})
    p.set_coordination_store(CoordinationStore(db_path=db, character="hero"))
    observer = CoordinationStore(db_path=db, character="observer")
    seen: list[dict[str, int]] = []

    def _spy(*_args, **_kwargs):
        seen.append(observer.sibling_bank_claims(datetime.now(tz=timezone.utc)))
        raise ApiActionError(478, "Missing required item(s)")

    action = WithdrawItemAction(code="sap", quantity=111, bank_location=(4, 0))
    char = make_char_schema(x=4, y=0)
    empty = MagicMock()
    empty.data = []
    items_patch, details_patch = _bank_sync_patches([])
    try:
        with redirect_stdout(io.StringIO()):
            with patch("artifactsmmo_cli.ai.actions.withdraw_item.withdraw_item",
                       side_effect=_spy), \
                 patch("artifactsmmo_cli.ai.player.get_character",
                       return_value=make_get_character_result(char)), \
                 patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty), \
                 patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty), \
                 items_patch, details_patch:
                _new_state, outcome = p._execute(action, MagicMock())
        assert outcome == "error:HTTP_478"
        assert seen == [{"sap": 111}], "the claim must be visible to siblings before the request"
    finally:
        p._coordination.close()
        observer.close()


def test_execute_releases_the_claim_when_the_withdraw_is_rejected(tmp_path):
    """A structured server rejection means the withdraw did not happen — 478
    "Missing required item(s)" above all, the very case where the units belong
    to someone else. Holding the claim would compound the contention this
    mechanism exists to relieve."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(x=4, y=0, bank_items={"sap": 111})
    p.set_coordination_store(CoordinationStore(db_path=db, character="hero"))
    observer = CoordinationStore(db_path=db, character="observer")
    action = WithdrawItemAction(code="sap", quantity=111, bank_location=(4, 0))
    char = make_char_schema(x=4, y=0)
    empty = MagicMock()
    empty.data = []
    items_patch, details_patch = _bank_sync_patches([])
    try:
        with redirect_stdout(io.StringIO()):
            with patch("artifactsmmo_cli.ai.actions.withdraw_item.withdraw_item",
                       side_effect=ApiActionError(478, "Missing required item(s)")), \
                 patch("artifactsmmo_cli.ai.player.get_character",
                       return_value=make_get_character_result(char)), \
                 patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty), \
                 patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty), \
                 items_patch, details_patch:
                _new_state, outcome = p._execute(action, MagicMock())
        assert outcome == "error:HTTP_478"
        assert observer.sibling_bank_claims(datetime.now(tz=timezone.utc)) == {}
    finally:
        p._coordination.close()
        observer.close()


def test_execute_releases_the_claim_when_the_withdraw_is_rate_limited(tmp_path):
    """A 429 is rejected before it reaches game logic, so the units were never
    taken — the same release case as a structured rejection."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(x=4, y=0, bank_items={"sap": 111})
    p.set_coordination_store(CoordinationStore(db_path=db, character="hero"))
    observer = CoordinationStore(db_path=db, character="observer")
    action = WithdrawItemAction(code="sap", quantity=111, bank_location=(4, 0))
    try:
        with redirect_stdout(io.StringIO()):
            with patch("artifactsmmo_cli.ai.actions.withdraw_item.withdraw_item",
                       side_effect=RateLimitedError({"Retry-After": "1"})), \
                 patch("artifactsmmo_cli.ai.player.time.sleep"):
                _new_state, outcome = p._execute(action, MagicMock())
        assert outcome == GamePlayer.RATE_LIMITED_OUTCOME
        assert observer.sibling_bank_claims(datetime.now(tz=timezone.utc)) == {}
    finally:
        p._coordination.close()
        observer.close()


def test_execute_keeps_the_claim_when_the_withdraw_succeeds(tmp_path):
    """THE deviation from "release on success", and the reason the mechanism is
    not inert.

    The reason a claim must be released is that a claim outliving its withdraw
    is stock nobody can touch. After a SUCCESSFUL withdraw the units are gone,
    so the claim withholds nothing that exists — what it shadows is the sibling
    snapshots that still show them, which IS the race: `bank_items` is only
    re-read after that sibling's own bank action or every
    `BANK_REFRESH_INTERVAL` actions. Releasing here would collapse the useful
    window to one HTTP round-trip. It expires on `BANK_CLAIM_TTL_SECONDS`
    instead, which is sized for exactly that settlement window."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(x=4, y=0, bank_items={"sap": 111})
    p.set_coordination_store(CoordinationStore(db_path=db, character="hero"))
    observer = CoordinationStore(db_path=db, character="observer")
    action = WithdrawItemAction(code="sap", quantity=5, bank_location=(4, 0))
    char = make_char_schema(x=4, y=0)
    items_patch, details_patch = _bank_sync_patches([])
    try:
        with redirect_stdout(io.StringIO()):
            with patch("artifactsmmo_cli.ai.actions.withdraw_item.withdraw_item",
                       return_value=make_api_result(char)), \
                 items_patch, details_patch:
                _new_state, outcome = p._execute(action, MagicMock())
        assert outcome == "ok"
        now = datetime.now(tz=timezone.utc)
        assert observer.sibling_bank_claims(now) == {"sap": 5}
        # ...and it is genuinely TTL-bounded, not permanent.
        assert observer.sibling_bank_claims(
            now + timedelta(seconds=BANK_CLAIM_TTL_SECONDS + 1)) == {}
    finally:
        p._coordination.close()
        observer.close()


def test_execute_claims_nothing_for_a_non_withdraw_action(tmp_path):
    """The other side of the `isinstance` gate: only a withdraw takes bank
    stock, so only a withdraw announces one."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(x=0, y=0)
    p.set_coordination_store(CoordinationStore(db_path=db, character="hero"))
    observer = CoordinationStore(db_path=db, character="observer")
    char = make_char_schema(x=3, y=5)
    try:
        with redirect_stdout(io.StringIO()):
            with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                       return_value=make_api_result(char)):
                _new_state, outcome = p._execute(MoveAction(x=3, y=5), MagicMock())
        assert outcome == "ok"
        assert observer.sibling_bank_claims(datetime.now(tz=timezone.utc)) == {}
    finally:
        p._coordination.close()
        observer.close()


def test_update_coordination_reads_sibling_order_claims(tmp_path):
    """The read half, wired: an order a sibling committed to cancelling reaches
    `SelectionContext.sibling_order_claims`, which is what `cancel_targets`
    filters on."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    try:
        sibling.claim_ge_order("order-1", datetime.now(tz=timezone.utc))
        p._update_coordination(p.state, p.game_data)
        assert p._sibling_order_claims == frozenset({"order-1"})
        assert p._selection_context(
            combat_monster=None).sibling_order_claims == frozenset({"order-1"})
    finally:
        store.close()
        sibling.close()


def test_update_coordination_clears_sibling_order_claims_without_a_store():
    """The single-character path, and the bit-identical guarantee: with no store
    the claim set is EMPTY, not stale, so `cancel_targets` reports exactly what
    it reported before this feature existed."""
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    p._sibling_order_claims = frozenset({"order-1"})  # prove it is CLEARED
    p._update_coordination(p.state, p.game_data)
    assert p._coordination is None
    assert p._sibling_order_claims == frozenset()
    assert p._selection_context(combat_monster=None).sibling_order_claims == frozenset()


def test_a_character_never_reads_back_its_own_order_claim(tmp_path):
    """Self-exclusion end to end: after committing to a cancel, this character's
    own target set must NOT shrink — it would stop planning the very cancel it
    is executing."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    store = CoordinationStore(db_path=db, character="hero")
    p.set_coordination_store(store)
    try:
        store.claim_ge_order("order-1", datetime.now(tz=timezone.utc))
        p._update_coordination(p.state, p.game_data)
        assert p._sibling_order_claims == frozenset()
    finally:
        store.close()


def test_claim_ge_order_is_a_noop_without_a_store():
    p = GamePlayer(character="hero")
    p._claim_ge_order(GeCancelOrderAction(order_id="order-1", ge_location=(0, 0)))


def test_release_ge_orders_is_a_noop_without_a_store():
    p = GamePlayer(character="hero")
    p._release_ge_orders(GeCancelOrderAction(order_id="order-1", ge_location=(0, 0)))


def test_release_ge_orders_leaves_a_claim_alone_for_a_non_cancel_action(tmp_path):
    """`_release_ge_orders` is called from the failure branches for EVERY
    action, so it has to distinguish. A Move that fails must not un-hide the
    order an in-flight cancel is holding."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    store = CoordinationStore(db_path=db, character="hero")
    observer = CoordinationStore(db_path=db, character="observer")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        store.claim_ge_order("order-1", now)
        p._release_ge_orders(MoveAction(x=1, y=1))
        assert observer.sibling_order_claims(now) == frozenset({"order-1"})
        p._release_ge_orders(GeCancelOrderAction(order_id="order-1", ge_location=(0, 0)))
        assert observer.sibling_order_claims(now) == frozenset()
    finally:
        store.close()
        observer.close()


def test_execute_publishes_the_order_claim_before_the_cancel_request(tmp_path):
    """ORDERING is the whole mechanism: a claim published after the request
    would be invisible to the sibling deriving its own cancel targets right now.
    The assertion runs INSIDE the patched API call, so it can only pass if the
    claim landed first."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(x=5, y=1)
    p.set_coordination_store(CoordinationStore(db_path=db, character="hero"))
    observer = CoordinationStore(db_path=db, character="observer")
    seen: list[frozenset[str]] = []

    def _spy(*_args, **_kwargs):
        seen.append(observer.sibling_order_claims(datetime.now(tz=timezone.utc)))
        raise ApiActionError(404, "Order not found.")

    action = GeCancelOrderAction(order_id="order-1", ge_location=(5, 1))
    char = make_char_schema(x=5, y=1)
    empty = MagicMock()
    empty.data = []
    try:
        with redirect_stdout(io.StringIO()):
            with patch("artifactsmmo_cli.ai.actions.ge_cancel_order.action_ge_cancel_order",
                       side_effect=_spy), \
                 patch("artifactsmmo_cli.ai.player.get_character",
                       return_value=make_get_character_result(char)), \
                 patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty), \
                 patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty):
                _new_state, outcome = p._execute(action, MagicMock())
        assert outcome == "error:HTTP_404"
        assert seen == [frozenset({"order-1"})], \
            "the claim must be visible to siblings before the request"
    finally:
        p._coordination.close()
        observer.close()


def test_execute_releases_the_order_claim_when_the_cancel_is_rejected(tmp_path):
    """HTTP 404 "Order not found" is the exact error this mechanism exists to
    stop, and when it happens anyway the order is gone — so the claim describes
    nothing and must not keep hiding an id for the rest of its TTL."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(x=5, y=1)
    p.set_coordination_store(CoordinationStore(db_path=db, character="hero"))
    observer = CoordinationStore(db_path=db, character="observer")
    action = GeCancelOrderAction(order_id="order-1", ge_location=(5, 1))
    char = make_char_schema(x=5, y=1)
    empty = MagicMock()
    empty.data = []
    try:
        with redirect_stdout(io.StringIO()):
            with patch("artifactsmmo_cli.ai.actions.ge_cancel_order.action_ge_cancel_order",
                       side_effect=ApiActionError(404, "Order not found.")), \
                 patch("artifactsmmo_cli.ai.player.get_character",
                       return_value=make_get_character_result(char)), \
                 patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty), \
                 patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty):
                _new_state, outcome = p._execute(action, MagicMock())
        assert outcome == "error:HTTP_404"
        assert observer.sibling_order_claims(datetime.now(tz=timezone.utc)) == frozenset()
    finally:
        p._coordination.close()
        observer.close()


def test_execute_keeps_the_order_claim_when_the_cancel_succeeds(tmp_path):
    """On success the order really is gone, so the claim withholds nothing that
    exists — what it does is shadow the sibling snapshots that still list it,
    which is the whole race. Left to expire on GE_ORDER_CLAIM_TTL_SECONDS, and
    genuinely TTL-bounded rather than permanent — that bound is what keeps
    `EscrowConservation`'s "no capital locked forever" pairing honest."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state(x=5, y=1)
    p.set_coordination_store(CoordinationStore(db_path=db, character="hero"))
    observer = CoordinationStore(db_path=db, character="observer")
    action = GeCancelOrderAction(order_id="order-1", ge_location=(5, 1))
    char = make_char_schema(x=5, y=1)
    try:
        with redirect_stdout(io.StringIO()):
            with patch("artifactsmmo_cli.ai.actions.ge_cancel_order.action_ge_cancel_order",
                       return_value=make_api_result(char)):
                _new_state, outcome = p._execute(action, MagicMock())
        assert outcome == "ok"
        now = datetime.now(tz=timezone.utc)
        assert observer.sibling_order_claims(now) == frozenset({"order-1"})
        assert observer.sibling_order_claims(
            now + timedelta(seconds=GE_ORDER_CLAIM_TTL_SECONDS + 1)) == frozenset()
    finally:
        p._coordination.close()
        observer.close()


# ---------------------------------------------------------------------------
# GamePlayer._update_coordination — the real self_servable set (Task 3 of the
# role_driven_supply spec). Replaces the frozenset() placeholder that used to
# be passed to `publish_demand`, so every published row is no longer
# unconditionally read back as "the requester cannot make this". Also threads
# `sibling_demand_asymmetric` onto `SelectionContext.asymmetric_demand`, the
# signal Task 4's supply rung gates on.
# ---------------------------------------------------------------------------

def _self_servable_gd() -> GameData:
    """`greater_wooden_staff` gates at WEAPONCRAFTING 10 — the real API
    requirement (`items.greater_wooden_staff.craft` in the committed
    `gamedata_bundle.json`), a gate a low-level character genuinely cannot
    clear, not an absent one. It was written here as woodcutting 20, which
    is a fact the game does not contain: weaponcrafting is owned by `miner`
    and NOT by `logger`, so a fixture claiming woodcutting silently pointed
    the whole asymmetry story at the wrong role.
    `copper_ore` gathers at mining 1 — a gate any miner clears."""
    gd = GameData()
    gd._item_stats = {
        "greater_wooden_staff": ItemStats(code="greater_wooden_staff", level=10,
                                          type_="weapon", crafting_skill="weaponcrafting",
                                          crafting_level=10),
    }
    gd._crafting_recipes = {}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    return gd


def _player_with_coordination(
    tmp_path, name: str, db: str | None = None,
) -> tuple[GamePlayer, CoordinationStore]:
    """A character wired to a real coordination store over `_self_servable_gd`,
    following the construction style `_held_miner` above already uses. Holds
    `logger` (owns woodcutting) by default so a bare `_pick_supply_target`
    call has a role to rank against without a prior `_update_coordination`
    cold start — callers needing a different role override `p._role`
    afterward, same as `_held_miner`'s callers already do.

    `db` lets two characters share ONE on-disk store explicitly (the
    supply-claim tests below, `ai/supply_claim_and_batch` Task 3), rather than
    inventing a second construction style — every OTHER caller already gets
    the same path for free since `tmp_path` is one fixture instance per
    test."""
    resolved_db = db if db is not None else str(tmp_path / "coord.db")
    p = GamePlayer(character=name)
    p.state = make_state()
    p.game_data = _self_servable_gd()
    p._role = "logger"
    store = CoordinationStore(db_path=resolved_db, character=name)
    p.set_coordination_store(store)
    return p, store


def _publish_sibling_request(tmp_path, name: str, demand: dict[str, int],
                             self_servable: frozenset[str]) -> None:
    """Publish `demand` from a sibling character through a second store handle
    onto the SAME db `_player_with_coordination` uses."""
    db = str(tmp_path / "coord.db")
    sibling = CoordinationStore(db_path=db, character=name)
    try:
        sibling.publish_demand(demand, self_servable, datetime.now(tz=timezone.utc))
    finally:
        sibling.close()


def test_a_character_publishes_its_own_inability_to_make_what_it_wants(tmp_path):
    """Lor is at weaponcrafting 1; a greater_wooden_staff gates at
    weaponcrafting 10, so its request must go out marked for a sibling."""
    player, store = _player_with_coordination(tmp_path, "Lor")
    player.state = make_state(skills={"weaponcrafting": 1, "mining": 8})
    player._last_decide_crafting_target = "greater_wooden_staff"

    player._update_coordination(player.state, player.game_data)

    with SqlSession(store._engine) as s:
        rows = {r.item_code: r.self_servable for r in s.exec(select(MaterialDemand)).all()}
    assert rows["greater_wooden_staff"] is False


def test_a_character_that_can_make_its_own_material_says_so(tmp_path):
    player, store = _player_with_coordination(tmp_path, "Lor")
    player.state = make_state(skills={"mining": 20})
    player._last_decide_crafting_target = "copper_ore"

    player._update_coordination(player.state, player.game_data)

    with SqlSession(store._engine) as s:
        rows = {r.item_code: r.self_servable for r in s.exec(select(MaterialDemand)).all()}
    assert rows["copper_ore"] is True


def test_a_material_with_no_producing_skill_at_all_is_self_servable(tmp_path):
    """A vendor-only good like `lich_race_trophy` has NO producing skill —
    `game_data.producing_requirement` returns None — and must publish as
    SELF-SERVABLE, i.e. never advertised as asymmetric.

    THIS TEST WAS THE OPPOSITE, and the opposite made the whole supply rung
    inert: the consumer side, `_pick_supply_target`, SKIPS every code whose
    producing skill is None (no role owns a skill for it), so no character
    can ever be selected to serve one. Publishing such a code as asymmetric
    advertises help nobody can give — and on the live board that class was
    100% of the demand (`lich_race_medal`, `lich_race_trophy`: vendor
    purchases with no producing skill at all).

    `self_servable` means "the asker can obtain this without help". For a
    vendor-only item the asker can buy it exactly as well as any sibling, so
    there is no asymmetry for a sibling to exploit. ASYMMETRY IS STRICTLY
    ABOUT SKILL GATES."""
    player, store = _player_with_coordination(tmp_path, "Lor")
    gd = player.game_data
    gd._item_stats = {**gd._item_stats,
                      "mystic_ward": ItemStats(code="mystic_ward", level=1,
                                               type_="weapon",
                                               crafting_skill="weaponcrafting",
                                               crafting_level=1)}
    gd._crafting_recipes = {"mystic_ward": {"unobtainium": 1}}
    player.state = make_state(skills={"weaponcrafting": 1})
    player._last_decide_crafting_target = "mystic_ward"

    player._update_coordination(player.state, player.game_data)

    with SqlSession(store._engine) as s:
        rows = {r.item_code: r.self_servable for r in s.exec(select(MaterialDemand)).all()}
    assert rows["unobtainium"] is True


def test_a_skill_gated_request_reaches_a_capable_sibling_as_asymmetric(tmp_path):
    """THE asymmetry the feature exists for, end to end over one shared DB:
    the asker HAS the producing skill but is below the level the item gates
    at, so it publishes `self_servable=False`; a sibling that HAS the level
    reads the same row back as asymmetric and picks it as its supply target.

    Both halves in one test on purpose — publishing the flag and reading it
    were each covered alone, so a publisher/consumer DISAGREEMENT (exactly
    the defect that made this rung inert for skill-less codes) could not
    fail anything. Lor at weaponcrafting 1 cannot craft a greater_wooden_staff
    (weaponcrafting 10); R2D2 at weaponcrafting 10 can, and `miner` is the
    role that owns weaponcrafting."""
    asker, store = _player_with_coordination(tmp_path, "Lor")
    asker.state = make_state(skills={"weaponcrafting": 1, "mining": 8})
    asker._last_decide_crafting_target = "greater_wooden_staff"
    asker._update_coordination(asker.state, asker.game_data)

    with SqlSession(store._engine) as s:
        rows = {r.item_code: r.self_servable for r in s.exec(select(MaterialDemand)).all()}
    assert rows["greater_wooden_staff"] is False

    server, _ = _player_with_coordination(tmp_path, "R2D2")
    server.state = make_state(bank_items={}, skills={"weaponcrafting": 10, "mining": 10})
    server._role = "miner"
    server._update_coordination(server.state, server.game_data)

    assert "greater_wooden_staff" in server._asymmetric_demand
    assert server._supply_target is not None
    assert server._supply_target[0] == "greater_wooden_staff"


def test_the_asymmetric_set_reaches_the_selection_context(tmp_path):
    player, _ = _player_with_coordination(tmp_path, "R2D2")
    _publish_sibling_request(tmp_path, "Lor", {"greater_wooden_staff": 1}, self_servable=frozenset())

    player._update_coordination(player.state, player.game_data)
    ctx = player._selection_context(combat_monster=None)

    assert "greater_wooden_staff" in ctx.asymmetric_demand


def test_no_coordination_store_leaves_the_asymmetric_set_empty():
    """The single-character path: a stale set from a store that has since
    been detached must not survive — the same "prove it gets CLEARED, not
    left stale" pattern `test_update_coordination_clears_sibling_bank_claims_
    without_a_store` uses for `_sibling_bank_claims`. Pre-seeding a non-empty
    value is what makes this pin the reset at the top of `_update_coordination`
    rather than merely restate the `__init__` default, which would pass
    whether or not that reset exists."""
    player = GamePlayer(character="solo")
    player.state = make_state()
    player._asymmetric_demand = frozenset({"stale_code"})  # prove it gets CLEARED
    player._update_coordination(player.state, player.game_data)
    assert player._asymmetric_demand == frozenset()


# ---------------------------------------------------------------------------
# GamePlayer._pick_supply_target — ranking by asymmetry (Task 5 of the
# role_driven_supply spec). Both items below share ONE role's owned skills
# (`miner` owns {mining, weaponcrafting}) so they are genuine rivals under the
# `serves_item`/owned-skill gate, not one excluded by role before ranking
# ever runs — a cross-skill pairing would let `mystic_ward` win by default
# regardless of the fix, pinning nothing.
# ---------------------------------------------------------------------------

def test_a_request_only_i_can_fill_outranks_a_bigger_one_anyone_could(tmp_path):
    player, _ = _player_with_coordination(tmp_path, "R2D2")
    player._role = "miner"  # owns {mining, weaponcrafting}
    player._asymmetric_demand = frozenset({"mystic_ward"})
    item_demand = {"copper_ore": 30, "mystic_ward": 1}

    target = player._pick_supply_target(
        item_demand, {"copper_ore": "mining", "mystic_ward": "weaponcrafting"},
        make_state(bank_items={}, skills={"mining": 20, "weaponcrafting": 20}),
        {"copper_ore": 1, "mystic_ward": 10})

    assert target is not None and target[0] == "mystic_ward"


def test_among_equals_the_bigger_request_still_wins(tmp_path):
    player, _ = _player_with_coordination(tmp_path, "R2D2")
    player._role = "miner"
    player._asymmetric_demand = frozenset()
    item_demand = {"copper_ore": 30, "mystic_ward": 5}

    target = player._pick_supply_target(
        item_demand, {"copper_ore": "mining", "mystic_ward": "weaponcrafting"},
        make_state(bank_items={}, skills={"mining": 20, "weaponcrafting": 20}),
        {"copper_ore": 1, "mystic_ward": 1})

    assert target is not None and target[0] == "copper_ore"


# ---------------------------------------------------------------------------
# GamePlayer._pick_supply_target — one producer, one batch, per sibling
# request (`ai/supply_claim_and_batch` Task 3). Measured live: one request,
# `SupplyBank(spruce_wood x60)`, was served SIMULTANEOUSLY by R2D2 (225
# gathers) and Robby (231 gathers) — 456 units against a 60-unit ask — while
# the target's identity churned `x50 -> x60 -> x81 -> x116 -> x129` on every
# cycle. Task 1's `claim_supply`/`supply_claim_holder`/`release_supply` and
# Task 2's `supply_batch_target_pure` are wired in here.
# ---------------------------------------------------------------------------

def test_an_item_a_sibling_is_already_producing_is_skipped(tmp_path):
    """The measured bug: R2D2 and Robby each spent ~230 gathers on the same
    60-unit spruce_wood request."""
    db = str(tmp_path / "coord.db")
    CoordinationStore(db_path=db, character="R2D2").claim_supply("spruce_wood", NOW)
    player, _ = _player_with_coordination(tmp_path, "Robby", db=db)

    target = player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}), {"spruce_wood": 1})

    assert target is None


def test_a_sibling_held_item_is_never_offered_to_the_claim_election(tmp_path, monkeypatch):
    """The single-candidate return value above (`target is None`) cannot tell
    the skip apart from removing it: with only one candidate, the excluded-
    on-loss retry loop at the bottom of `_pick_supply_target` reaches the
    SAME `None` either way, because `claim_supply` itself refuses a
    sibling-held item just as reliably as the ranking skip does — proven by
    running the actual mutant (deleting the skip block) against the test
    above and watching it PASS. What only the ranking skip prevents is ever
    OFFERING a sibling-held candidate to `claim_supply` in the first place:
    with two candidates, one sibling-held and one free, the skip must keep
    `claim_supply` from ever being called with the sibling-held code, even
    though the free code still wins in the end regardless."""
    db = str(tmp_path / "coord.db")
    CoordinationStore(db_path=db, character="R2D2").claim_supply("spruce_wood", NOW)
    player, store = _player_with_coordination(tmp_path, "Robby", db=db)
    attempted: list[str] = []
    real_claim_supply = store.claim_supply
    monkeypatch.setattr(
        store, "claim_supply",
        lambda code, now: (attempted.append(code), real_claim_supply(code, now))[1])

    target = player._pick_supply_target(
        {"spruce_wood": 60, "ash_wood": 5},
        {"spruce_wood": "woodcutting", "ash_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}, bank_items={}),
        {"spruce_wood": 1, "ash_wood": 1})

    assert target is not None and target[0] == "ash_wood"
    assert "spruce_wood" not in attempted


def test_my_own_claim_does_not_block_me_from_continuing(tmp_path):
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "R2D2", db=db)
    store.claim_supply("spruce_wood", NOW)

    # `bank_items={}` (visited, empty) rather than the `make_state()` default
    # of "never visited" — see `test_pick_supply_target_none_when_the_bank_
    # has_never_been_visited` above for why an unvisited bank returns None
    # regardless of the claim outcome this test pins.
    target = player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}, bank_items={}), {"spruce_wood": 1})

    assert target is not None and target[0] == "spruce_wood"


def test_choosing_an_item_claims_it_for_this_character(tmp_path):
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "Robby", db=db)

    player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}), {"spruce_wood": 1})

    assert store.supply_claim_holder("spruce_wood", NOW) == "Robby"


def test_the_target_is_one_batch_not_the_whole_demand(tmp_path):
    """456 units were produced against a 60-unit ask because the commitment was
    the whole demand against a moving bank count."""
    db = str(tmp_path / "coord.db")
    player, _ = _player_with_coordination(tmp_path, "Robby", db=db)

    target = player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}, bank_items={"spruce_wood": 0}),
        {"spruce_wood": 1})

    assert target is not None
    assert target[1] == SUPPLY_BATCH      # not 60
    assert target[2] == 60                # the unmet demand is reported unchanged


def test_switching_items_releases_the_previous_claim(tmp_path):
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "Robby", db=db)
    store.claim_supply("spruce_wood", NOW)
    # What Robby was serving as of the END of the previous cycle — the field
    # `_update_coordination` assigns `_pick_supply_target`'s return value into,
    # and the ONLY record (this character keeps no second one) of "stop
    # serving THIS item" that a switch reads.
    player._supply_target = ("spruce_wood", 60, 60)

    player._pick_supply_target(
        {"iron_ore": 80}, {"iron_ore": "mining"},
        make_state(skills={"mining": 20}), {"iron_ore": 1})

    assert store.supply_claim_holder("spruce_wood", NOW) is None


def _spy_on_claims(monkeypatch, store) -> list[str]:
    """Record every item code offered to `claim_supply`, real behaviour intact.

    A claim is RENEWED by re-claiming it (`claim_supply` extends the current
    holder's row in place), so "did this character renew?" is exactly "was the
    code passed to `claim_supply`?" — and the TTL is 600s of wall clock, which
    no test can watch expire. The same spy idiom
    `test_a_sibling_held_item_is_never_offered_to_the_claim_election` above
    already uses, hoisted so the renewal tests share one construction."""
    attempted: list[str] = []
    real_claim_supply = store.claim_supply
    monkeypatch.setattr(
        store, "claim_supply",
        lambda code, now: (attempted.append(code), real_claim_supply(code, now))[1])
    return attempted


def test_a_holder_that_did_not_produce_last_cycle_stops_renewing(tmp_path, monkeypatch):
    """The claim must be held while PRODUCING, not merely while wanting to.

    A character whose SUPPLY_BANK rung fires but which loses selection every
    cycle — to a guard, or to a higher-value goal — used to renew its claim
    unconditionally, holding the item against the whole fleet forever: renewal
    was wired to RANKING, and ranking runs on every cycle regardless of what
    the arbiter then chose. Not renewing lets `DEMAND_TTL_SECONDS` reap it,
    which is the whole reason the claim has an expiry."""
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "Robby", db=db)
    store.claim_supply("spruce_wood", NOW)
    player._supply_target = ("spruce_wood", SUPPLY_BATCH, 60)
    player._last_goal_name = "RestoreHP()"       # a guard won selection instead
    attempted = _spy_on_claims(monkeypatch, store)

    target = player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}, bank_items={}), {"spruce_wood": 1})

    assert attempted == []
    # It keeps TARGETING the item: the claim lapsing is what hands the item
    # back, and a character that wins selection again before the TTL runs out
    # resumes producing (and renewing) without a detour.
    assert target is not None and target[0] == "spruce_wood"


def test_a_holder_that_produced_last_cycle_renews(tmp_path, monkeypatch):
    """The other half: a character actually running SupplyBank for the item
    must keep its claim, or a production run longer than the TTL would lose the
    item to a sibling mid-batch."""
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "Robby", db=db)
    store.claim_supply("spruce_wood", NOW)
    player._supply_target = ("spruce_wood", SUPPLY_BATCH, 60)
    player._last_goal_name = f"SupplyBank(spruce_woodx{SUPPLY_BATCH})"
    attempted = _spy_on_claims(monkeypatch, store)

    player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}, bank_items={}), {"spruce_wood": 1})

    assert attempted == ["spruce_wood"]
    assert store.supply_claim_holder("spruce_wood", NOW) == "Robby"


def test_renewal_matches_the_item_not_the_batch_quantity(tmp_path, monkeypatch):
    """The quantity in `SupplyBankGoal`'s repr moves from batch to batch BY
    DESIGN (`supply_batch_target_pure`), so a whole-repr match would read "did
    not produce" on exactly the cycles where the character just finished a
    batch — reaping the claim of the hardest-working producer. Last cycle
    served the x10 batch; this cycle's target is the x20 one."""
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "Robby", db=db)
    store.claim_supply("spruce_wood", NOW)
    player._supply_target = ("spruce_wood", SUPPLY_BATCH, 60)
    player._last_goal_name = f"SupplyBank(spruce_woodx{SUPPLY_BATCH})"
    attempted = _spy_on_claims(monkeypatch, store)

    target = player._pick_supply_target(
        {"spruce_wood": 50}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}, bank_items={"spruce_wood": SUPPLY_BATCH}),
        {"spruce_wood": 1})

    assert target is not None and target[1] == 2 * SUPPLY_BATCH   # a NEW batch
    assert attempted == ["spruce_wood"]


def test_a_first_pick_claims_without_having_produced_anything_yet(tmp_path, monkeypatch):
    """Acquisition is not renewal: a character that was serving something else
    (or nothing) has by definition not produced this item yet, and gating the
    FIRST claim on production would mean no character could ever take one."""
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "Robby", db=db)
    player._supply_target = ("ash_wood", SUPPLY_BATCH, 5)
    player._last_goal_name = "SupplyBank(ash_woodx10)"
    attempted = _spy_on_claims(monkeypatch, store)

    player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}, bank_items={}), {"spruce_wood": 1})

    assert attempted == ["spruce_wood"]
    assert store.supply_claim_holder("spruce_wood", NOW) == "Robby"


def test_losing_the_role_hands_the_claim_back(tmp_path):
    """A character with no role produces nothing, so it must not sit on a
    claim for the rest of the TTL: the no-role exit is a stop-serving event
    exactly like switching items is."""
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "Robby", db=db)
    store.claim_supply("spruce_wood", NOW)
    player._supply_target = ("spruce_wood", SUPPLY_BATCH, 60)
    player._role = None

    assert player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}, bank_items={}), {"spruce_wood": 1}) is None
    assert store.supply_claim_holder("spruce_wood", NOW) is None


def test_an_unknown_role_hands_the_claim_back(tmp_path):
    """Same for a held role name the catalog no longer knows — the other exit
    that leaves this character with no owned skills to produce with."""
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "Robby", db=db)
    store.claim_supply("spruce_wood", NOW)
    player._supply_target = ("spruce_wood", SUPPLY_BATCH, 60)
    player._role = "no_such_role"

    assert player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}, bank_items={}), {"spruce_wood": 1}) is None
    assert store.supply_claim_holder("spruce_wood", NOW) is None


def test_a_lost_supply_claim_falls_through_to_the_next_candidate(tmp_path, monkeypatch):
    """A sibling can win the SAME item's election in the gap between this
    character's skip-check and its own claim attempt, in the same cycle.
    `claim_supply` returning False for that is ordinary contention (see its
    own docstring), not an error: the character must fall through to its
    next-best candidate rather than commit to producing into a race it just
    lost."""
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "Robby", db=db)
    real_claim_supply = store.claim_supply
    monkeypatch.setattr(
        store, "claim_supply",
        lambda code, now: False if code == "spruce_wood" else real_claim_supply(code, now))

    target = player._pick_supply_target(
        {"spruce_wood": 60, "ash_wood": 5},
        {"spruce_wood": "woodcutting", "ash_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}, bank_items={}),
        {"spruce_wood": 1, "ash_wood": 1})

    assert target is not None and target[0] == "ash_wood"
    assert store.supply_claim_holder("ash_wood", NOW) == "Robby"


# ---------------------------------------------------------------------------
# The read-only planning path sees the fleet — without joining it.
#
# `plan <char>` never called `_update_coordination` (it runs only in `run()`'s
# loop), so every coordination field was stale-empty in the `plan`, `objective`
# and `combat-deficit` diagnostics. Invisible while the fields only DAMPENED
# things — a sibling's bank claim can only shrink a shed licence — and visible
# the moment the sibling ROUTE landed, because an empty `sibling_skills` turns a
# reachable recipe back into an unobtainable one.
# ---------------------------------------------------------------------------


def _coord_player(tmp_path, character: str = "C3P0"):  # type: ignore[no-untyped-def]
    db = str(tmp_path / "coord.db")
    player = GamePlayer(character=character)
    player.set_coordination_store(CoordinationStore(db_path=db, character=character))
    return player, db


def test_refresh_sibling_reads_populates_every_pure_read_field(tmp_path) -> None:
    """All four fields the selection context needs, from one shared reader."""
    now = datetime.now(tz=timezone.utc)
    CoordinationStore(db_path=str(tmp_path / "coord.db"),
                      character="Robby").publish_skills({"jewelrycrafting": 15}, now)
    player, _ = _coord_player(tmp_path)

    player._refresh_sibling_reads(now)

    assert player._sibling_skills == {"jewelrycrafting": 15}
    assert player._sibling_bank_claims == {}
    assert player._sibling_order_claims == frozenset()
    assert player._asymmetric_demand == frozenset()


def test_refresh_sibling_reads_publishes_nothing_and_claims_nothing(tmp_path) -> None:
    """THE SAFETY PROPERTY. A read-only command must not be able to change what
    the fleet does: publishing would put a diagnostic's snapshot on the shared
    board, and claiming would take an election away from a live child.

    Asserted against the TABLES rather than by inspecting the method, so a future
    edit that slips a publish or a claim into the reader fails here.
    """
    now = datetime.now(tz=timezone.utc)
    player, _db = _coord_player(tmp_path)

    player._refresh_sibling_reads(now)

    engine = player._coordination._engine
    with SqlSession(engine) as s:
        for table in ("skill_ledger", "material_demand", "holding_ledger",
                      "supply_claims", "turn_in_claims", "role_leases",
                      "bank_stock_claims", "ge_order_claims"):
            rows = s.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            assert rows == 0, f"the read-only refresh wrote to {table}"


def test_refresh_sibling_reads_is_a_no_op_without_coordination(tmp_path) -> None:
    """Every single-character run takes this path."""
    player = GamePlayer(character="solo")

    player._refresh_sibling_reads(datetime.now(tz=timezone.utc))

    assert player._sibling_skills == {}


# ---------------------------------------------------------------------------
# The BLOCKED target: what a skill-gated character asks the fleet for
# ---------------------------------------------------------------------------

def test_a_skill_gated_character_publishes_the_target_it_cannot_make():
    """THE ASK THAT WAS NEVER MADE.

    Demand is published from the chosen root, and a character blocked by a
    crafting-skill gate resolves to `ReachSkillLevel` — not an `ObtainItem` — so
    `_last_decide_crafting_target` is None and the whole board stays silent.
    Measured on the live fleet: `SupplyBank` has executed **0 times in 105,159
    cycles**, `supply_claims` is empty, and the only rows the board has ever
    carried are quantity-1 vendor goods every asker can serve itself.

    The item a sibling could actually help with — the one behind a skill gate —
    is precisely the one never asked for. So the blocked target is published
    too, from the walk that classified it, and `serves_item` then marks it NOT
    self-servable, which is what makes it ASYMMETRIC and what
    `SUPPLY_BANK`'s second arm fires on."""
    p = GamePlayer(character="hero")
    gd = _make_planner_gd()
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 2}}
    p._last_decide_crafting_target = None
    p._last_blocked_target = "copper_dagger"
    state = make_state(inventory={"copper_bar": 1})
    assert p._own_unmet_demand(state, gd) == {"copper_dagger": 1, "copper_bar": 1}


def test_both_roots_are_published_not_one_or_the_other():
    """"What I am working toward" and "what I am blocked out of" are DIFFERENT
    facts, and the fleet needs both.

    Publishing only the chosen root keeps the board silent about the skill gate
    — the asymmetric half, and the only half a sibling can act on. Publishing
    only the blocked target would drop the materials the character is actually
    collecting. `closure_demand` accumulates the max across roots into one dict,
    which is its documented usage, so this is two calls rather than a merge
    invented at the call site."""
    p = GamePlayer(character="hero")
    gd = _make_planner_gd()
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 2},
                            "iron_dagger": {"iron_bar": 3}}
    p._last_decide_crafting_target = "iron_dagger"
    p._last_blocked_target = "copper_dagger"
    assert p._own_unmet_demand(make_state(), gd) == {
        "iron_dagger": 1, "iron_bar": 3, "copper_dagger": 1, "copper_bar": 2}
