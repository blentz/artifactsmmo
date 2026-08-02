"""Wire cross-character role coordination into the per-cycle player loop
(emergent-specialization spec, Task 11).

`GamePlayer._update_coordination` is the seam: called once per cycle in
`run()` beside `self._gear_latch.update(...)`, it renews this character's
lease, publishes its own unmet closure demand, re-decides its role, and
recomputes `self._supply_target` — which `_selection_context` threads onto
`SelectionContext.supply_target` for the SUPPLY_BANK means (Tasks 9/10) to
read.

Coverage note: this project's coverage config sets `branch = false`, so every
conditional added by this task needs a test pinned to EACH outcome, not just
one execution reaching the line. See the paired tests below (`..._none`/
`..._some`, `..._without_role`/`..._with_role`, etc.).
"""

from datetime import datetime, timezone

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.supply_bank import SupplyBankGoal
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.role_catalog import ROLE_CATALOG
from artifactsmmo_cli.ai.role_selection import (
    ROLE_IDLE_DWELL_CYCLES,
    ROLE_MIN_HOLD_CYCLES,
    decide_role,
    demand_by_role,
)
from artifactsmmo_cli.ai.strategy_driver import map_means
from artifactsmmo_cli.ai.tiers.means import SUPPLY_DEMAND_MIN, MeansKind, _fires
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _make_planner_gd

_T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Tasks 2-7 composition (from the brief): the cold-start allocator converges
# two characters wanting the same top-demand role onto DISTINCT roles.
# ---------------------------------------------------------------------------

def test_two_stores_converge_on_distinct_roles(tmp_path) -> None:
    """The cold-start allocator: both characters want the same top-demand role,
    the UNIQUE constraint serializes them, and they end up on different roles."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    try:
        hal.publish_demand({"copper_bar": 10}, _T0)
        c3po.publish_demand({"ash_plank": 4}, _T0)
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
        assert hal.live_leases(_T0) == {held["HAL"]: "HAL", held["C3P0"]: "C3P0"}
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
    }
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    return gd


def test_producing_skill_prefers_the_craft_skill_when_craftable():
    assert _skill_gd().producing_skill("copper_bar") == "mining"


def test_producing_skill_falls_back_to_the_gathering_skill():
    # copper_ore has no ItemStats/crafting_skill entry, so it falls through
    # to the gather-skill map built from resource_drops/resource_skill.
    assert _skill_gd().producing_skill("copper_ore") == "mining"


def test_producing_skill_none_when_the_api_exposes_neither():
    assert _skill_gd().producing_skill("no_such_item") is None


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
    result = p._pick_supply_target({"copper_ore": 5}, {"copper_ore": "mining"}, make_state())
    assert result is None


def test_pick_supply_target_none_for_an_unknown_role():
    p = GamePlayer(character="hero")
    p._role = "not_a_real_role"
    result = p._pick_supply_target({"copper_ore": 5}, {"copper_ore": "mining"}, make_state())
    assert result is None


def test_pick_supply_target_ignores_demand_outside_the_role_skills():
    p = GamePlayer(character="hero")
    p._role = "miner"  # owns {mining, weaponcrafting}
    item_demand = {"ash_plank": 9}  # woodcutting/gearcrafting -> logger's territory
    skill_of_item = {"ash_plank": "woodcutting"}
    assert p._pick_supply_target(item_demand, skill_of_item, make_state()) is None


def test_pick_supply_target_picks_the_highest_demand_match():
    p = GamePlayer(character="hero")
    p._role = "miner"
    item_demand = {"copper_ore": 4, "iron_ore": 9}
    skill_of_item = {"copper_ore": "mining", "iron_ore": "mining"}
    state = make_state(bank_items={"iron_ore": 1})
    assert p._pick_supply_target(item_demand, skill_of_item, state) == ("iron_ore", 10, 9)


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
    assert p._pick_supply_target(item_demand, skill_of_item, state) is None


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
    assert p._pick_supply_target(item_demand, skill_of_item, state) == ("copper_ore", 3, 3)


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
        assert store.live_leases(datetime.now(tz=timezone.utc))[p._role] == "hero"
    finally:
        store.close()


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


def test_update_coordination_does_not_set_role_when_the_claim_loses_the_race(tmp_path, monkeypatch):
    """`CoordinationStore.claim` can return False (a sibling won the UNIQUE-
    constraint race between `decide_role` reading `live_leases` and this
    character's own `claim` call). `_update_coordination` must not commit to
    a role it never actually holds."""
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


def test_update_coordination_clears_a_stale_role_when_a_reclaim_loses_the_race(tmp_path, monkeypatch):
    """The critical defect: `decide_role` returns `claim=current` when THIS
    character's own lease lapsed (a stall) and a sibling took the role over
    via `live_leases` — the re-claim path, distinct from a cold-start claim.
    If that re-claim then loses the race, `self._role` must be cleared, not
    left stale: leaving it set makes the character renew a lease it does not
    hold (a no-op) and keep computing `_supply_target` for a role a sibling
    actually owns — every cycle, forever, since the same failing re-claim
    repeats identically next cycle. Two characters would end up specialized
    identically, defeating the whole feature."""
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
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="hero")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
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


def test_update_coordination_idle_release_does_not_immediately_reclaim(tmp_path):
    """The exact churn hole Task 6's `idle_released` ruling closes: with
    every OTHER role already leased to a sibling, `miner` is hero's only
    free role. Releasing it while idle must NOT be followed by reclaiming it
    on the very next re-decide — without `idle_released` threaded through,
    this is an infinite claim/hold/release loop that never actually frees
    the role for anyone."""
    db = str(tmp_path / "coord.db")
    p = GamePlayer(character="hero")
    p.state = make_state()
    p.game_data = _make_planner_gd()
    store = CoordinationStore(db_path=db, character="hero")
    sibling = CoordinationStore(db_path=db, character="rival")
    p.set_coordination_store(store)
    now = datetime.now(tz=timezone.utc)
    try:
        for role in ROLE_CATALOG:
            if role.name != "miner":
                assert sibling.claim(role.name, now) is True
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = ROLE_MIN_HOLD_CYCLES
        p._role_zero_demand_cycles = ROLE_IDLE_DWELL_CYCLES - 1

        p._update_coordination(p.state, p.game_data)
        assert p._role is None  # released: own demand is zero
        assert "miner" in p._role_idle_released

        # Re-decide again immediately: miner is STILL the only free role and
        # STILL has zero demand. Without idle_released this reclaims it.
        p._update_coordination(p.state, p.game_data)
        assert p._role is None
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
        sibling.publish_demand({"copper_ore": 5}, now)
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
        sibling.publish_demand({"copper_ore": 5}, now)
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
        sibling.publish_demand({"copper_ore": 5}, now)
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
        sibling.publish_demand({"copper_ore": SUPPLY_DEMAND_MIN + 2}, now)
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = 3  # below ROLE_MIN_HOLD_CYCLES: stays "miner"

        p._update_coordination(p.state, p.game_data)
        ctx = p._selection_context(combat_monster=None)
        assert ctx.supply_target == ("copper_ore", SUPPLY_DEMAND_MIN + 4,
                                     SUPPLY_DEMAND_MIN + 2)

        # The last two links: _fires (the means predicate) and map_means (the
        # goal factory) — exactly what StrategyArbiter.select calls.
        assert _fires(MeansKind.SUPPLY_BANK, p.state, gd, None, ctx) is True
        goal = map_means(MeansKind.SUPPLY_BANK, gd, ctx, p.state)
        assert isinstance(goal, SupplyBankGoal)
        assert goal._item_code == "copper_ore"
        assert goal._quantity == SUPPLY_DEMAND_MIN + 4
        assert goal._demand == SUPPLY_DEMAND_MIN + 2
        assert repr(goal) == f"SupplyBank(copper_orex{SUPPLY_DEMAND_MIN + 4})"
    finally:
        store.close()
        sibling.close()


def test_a_sub_threshold_coordinated_demand_is_targeted_but_never_fires(tmp_path):
    """End-to-end read-back of the 2026-08-01 gate: coordination still computes
    a supply target for a small sibling request (the board is unchanged), but
    `_fires` declines it, so the character keeps working its own objective
    instead of pausing for a handful of units the sibling can gather itself."""
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
        sibling.publish_demand({"copper_ore": SUPPLY_DEMAND_MIN - 1}, now)
        store.claim("miner", now)
        p._role = "miner"
        p._role_held_cycles = 3

        p._update_coordination(p.state, p.game_data)
        ctx = p._selection_context(combat_monster=None)
        assert ctx.supply_target == ("copper_ore", SUPPLY_DEMAND_MIN + 1,
                                     SUPPLY_DEMAND_MIN - 1)
        assert _fires(MeansKind.SUPPLY_BANK, p.state, gd, None, ctx) is False
    finally:
        store.close()
        sibling.close()
