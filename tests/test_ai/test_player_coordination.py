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

import pytest

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.supply_bank import SupplyBankGoal
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
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
from artifactsmmo_cli.ai.tiers.means import SUPPLY_DEMAND_MIN, MeansKind, _fires
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_role_selection import _LOR_SKILLS, _ROBBY_SKILLS
from tests.test_ai.test_strategy_driver import _make_planner_gd

_T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


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
# GamePlayer._role_owned_skills
# ---------------------------------------------------------------------------

def test_role_owned_skills_empty_without_a_held_role():
    p = GamePlayer(character="hero")
    assert p._role is None
    assert p._role_owned_skills() == frozenset()


def test_role_owned_skills_resolves_the_held_role():
    p = GamePlayer(character="hero")
    p._role = "miner"  # owns {mining, weaponcrafting}
    assert p._role_owned_skills() == frozenset({"mining", "weaponcrafting"})


def test_role_owned_skills_raises_for_an_unknown_role():
    """Unlike `_pick_supply_target` (a genuine data-availability case, so it
    degrades to `None`), `self._role` reaching here outside `ROLE_CATALOG` is
    a catalog/lease-store consistency failure — `decide_role` only ever
    claims a catalog name — so this raises rather than silently going
    role-less and losing the whole fifth ranking factor invisibly."""
    p = GamePlayer(character="hero")
    p._role = "not_a_real_role"
    with pytest.raises(ValueError, match="not in ROLE_CATALOG"):
        p._role_owned_skills()


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
    assert ctx.role_skills == frozenset()


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
        sibling.publish_demand({"ash_wood": 5}, now)
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
        sibling.publish_demand({"ash_wood": 5}, now)
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
        assert ctx.role_skills == frozenset({"mining", "weaponcrafting"})
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
    sibling.publish_demand({"copper_ore": 5}, now)
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
        sibling.publish_demand({"ash_wood": 5}, now)
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
        sibling.publish_demand({"iron_ore": 30, "ash_wood": 6},
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
        sibling.publish_demand({"iron_ore": 30, "copper_ore": 4}, now)
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
