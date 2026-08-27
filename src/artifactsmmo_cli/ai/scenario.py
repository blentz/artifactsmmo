"""Synthetic planner scenarios: a mock character + the real game catalog.

Phase 1 of the progression-tree spec (docs/superpowers/specs/
2026-07-06-progression-tree-design.md): golden scenario tests and the
`plan --scenario` CLI share these fixtures, so a planner change can be
exercised offline against realistic data before it ever runs live.

WAVE 3a FIX-ROUND 1 turned `derive_combat_stats` ON for the four GOLDEN
scenarios (`l1_fresh`, `l10_weapon_upgrade`, `l10_copper_adequate`,
`l12_taskgated_bag`). Two reasons, and the second is why it could not wait:

  * the zero-stat harness default asserts a world the API cannot produce — a
    level-12 character in a full copper set losing to a 60-hp chicken;
  * that fiction became LOAD-BEARING at the flip. The retired ranking read
    `near_term_gear`, capped by LEVEL and blind to winnability. The resolution
    walk reads `gear_targets_with_blockers`, which gears for
    `tier_progress.gear_target_tier` — the rung being CLEARED. With no attack
    nothing clears, so `gear_target_tier` pinned to 1 and all four goldens
    collapsed onto ONE answer, `GatherMaterials(ash_wood)`. A golden suite that
    cannot tell four scenarios apart is testing nothing.

Measured before and after: the four goldens went from 1 distinct outcome to 3.
`l10_weapon_upgrade` and `l12_taskgated_bag` still converge — recorded in
`.superpowers/sdd/PLAN_wave3a_cutover/task-6-report.md` rather than papered
over. The stats-OFF default is UNCHANGED for every other scenario; the ones
that deliberately rely on it (the L48 pair, the gearcrafting ramps) say so in
their own descriptions."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.raid_info import RaidInfo
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, SKILL_NAMES, WorldState

FAR_FUTURE = datetime(9999, 12, 31, tzinfo=timezone.utc)
"""Expiry used for scenario-declared active events: WorldState.active_events
maps event code -> tz-aware expiration, and an offline scenario means "this
event is up for the whole planning cycle", so the horizon is pinned far past
any planner arithmetic rather than sampled from a clock (determinism)."""


@dataclass(frozen=True)
class ScenarioCharacter:
    """A synthetic character for offline planning. Only game-legal values:
    item codes are validated against the catalog by the scenario tests."""
    name: str
    level: int = 1
    hp: int | None = None          # None -> max_hp
    max_hp: int = 120
    gold: int = 0
    skills: dict[str, int] = field(default_factory=dict)
    equipment: dict[str, str] = field(default_factory=dict)  # slot -> code
    inventory: dict[str, int] = field(default_factory=dict)
    inventory_max: int = 100
    inventory_slots_max: int | None = None
    """Explicit inventory SLOT cap override. None (default) makes
    `scenario_state` fall back to `inventory_max` (the QUANTITY cap, always
    >= distinct-stack count) rather than `len(inventory)` — the latter made
    every scenario read slots_used == slots_max (0 free) by construction,
    spuriously gating any consumer that reads `inventory_slots_free`
    (relief/gating logic). Defaulting to the quantity cap means slots never
    bind before quantity, preserving every existing scenario's exact
    pre-slot behavior. A scenario that wants to test slot limits sets this
    field explicitly."""
    bank: dict[str, int] | None = field(default_factory=dict)  # None = unknown
    bank_gold: int | None = None
    """Explicit KNOWN bank-gold override. None (default) preserves the legacy
    inference (0 when `bank` is known, None/unknown when `bank` is None) — set
    this to give a scenario bank gold distinct from pocket `gold` WITHOUT
    inflating `gold` itself. Needed because `state.gold` (pocket) and
    `state.bank_gold` are read by DIFFERENT consumers: `tiers/objective.py`'s
    `is_attainable_now` (near_term_gear candidacy) reads POCKET gold only,
    while `analyze_currency_leaves` (GAP-3/Task 3's reserve-aware gold-buy
    affordability) reads pocket + KNOWN bank gold. A scenario that needs extra
    TOTAL gold to clear the progression-reserve floor for one purchase, without
    also making an unrelated pricier near-term target look pocket-affordable
    and widening the candidate surface, ferries the extra gold through the
    bank instead of the pocket (see l30_rune_fill)."""
    task: tuple[str, str, int, int] | None = None  # code, type, progress, total
    utility_quantities: dict[str, int] = field(default_factory=dict)
    """utility1_slot/utility2_slot -> stocked quantity. WorldState defaults
    both to 0 (unstocked) even when `equipment` names a code in the slot —
    equipped_potion_qty treats a zero-quantity slot as unprovisioned, so a
    scenario that means to read as "utility slot already stocked" (e.g.
    band-adequate gear scenarios where a candidate must not re-appear for
    an already-held potion) must set this explicitly."""
    active_events: tuple[str, ...] = ()
    """Event codes live for the whole scenario cycle (converted to
    WorldState.active_events entries expiring at FAR_FUTURE). Validated
    against the bundle's event registry by the scenario tests, same as item
    codes. seed_offline mirrors the live player's per-cycle overlay by
    seeding GameData.active_event_codes from the state, so event
    monster/resource/NPC spawns surface exactly as they do live."""
    raids: tuple[tuple[str, str], ...] = ()
    """(raid_code, boss_monster_code) pairs live for the whole scenario cycle,
    converted to `WorldState.raids` entries with status="active". Mirrors
    `active_events`, with two differences worth stating:

    * `RaidInfo.is_active()` keys on the STATUS string, not a timestamp window, so
      a declared raid reads active by construction rather than via a far-future
      expiry.
    * The BOSS must be named explicitly. A raid's map-content code is NOT its
      monster code (`enchanted_fairy` is the content, `pixie` is the boss), and
      GameData carries no raid catalog to resolve one to the other -- `GET /raids`
      supplies that mapping live but is not in the cache bundle. Until the catalog
      lands, a scenario states the pair rather than a lookup pretending to exist.

    Exists so a scenario can exercise BOTH poles of a raid-gated decision -- no
    raid means the bot provably cannot plan, an active raid means it can. Without
    it only the negative pole is expressible, and the negative pole passes
    trivially (epic P3, docs/PLAN_events_raids_epic.md)."""
    derive_combat_stats: bool = False
    """When True, scenario_state computes the server-total combat stats
    (attack/dmg/dmg_elements/resistance/critical_strike/initiative) by
    summing the equipped items' catalog stats — the server reports totals =
    base 0 + gear, so this reproduces what a live character wearing this
    loadout would report. Requires game_data at scenario_state time.

    Also derives max_hp = 115 + 5*level + sum(equipped gear hp_bonus) — the
    same base-HP formula the server uses, live-validated against a real
    character (L10: 115 + 50 = 165 base, +gear; matched the live /character
    response). Under this flag the derived value REPLACES the scenario's
    hand-declared `max_hp`; a scenario opting into derive_combat_stats drops
    its own max_hp field (dead weight — it's overwritten either way).

    Default False: the pre-existing scenarios were all empirically pinned
    (goldens, band-adequate fixed points) under the harness's original
    zero-stat states, where `is_winnable` is False against EVERY monster
    (predict_win sees 0 attack). Flipping them retroactively would silently
    re-derive their pins, so realistic combat stats (including derived
    max_hp) are opt-in per scenario."""
    ge_market: bool = False
    """Which Grand-Exchange MARKET this scenario is planned in: the quiet book
    (False, no standing order on anything) or the order book captured into the
    bundle (True). Forwarded to `load_bundle_game_data(..., with_ge_orders=)`
    by every harness that plans a scenario, including `plan --scenario`.

    It lives on the character rather than on the loader because the market is
    part of what a scenario ASSERTS, exactly like `active_events` and `raids`:
    a GE-populated cell and its quiet control are the SAME character in two
    worlds, and a control the harness cannot name is a control nobody can run.
    Measured (see `GameData.from_cache_bundle`): with the book hydrated, an
    adequate-skill character standing on `iron_legs_armor` plans
    `GeBuy(iron_legs_armor)`; in the quiet book the same character plans
    `Gather(iron_rocks x42)`.

    Default False so every scenario written before the book existed keeps the
    market it was pinned in."""
    unlocked_achievements: tuple[str, ...] = ()
    """Account achievements this scenario's world has COMPLETED, on top of the
    ones the capture already marks. Forwarded to
    `load_bundle_game_data(..., completed_achievements=)` by every harness that
    plans a scenario, `plan --scenario` included — the same seam `ge_market`
    uses, and for the same reason: it is a property of the WORLD the character
    plans in, and a control the harness cannot name is a control nobody can run.

    Why a scenario needs it (coverage-matrix cell 11): an `achievement_unlocked`
    access condition is evaluated at map build, so an unmet one deletes the tile
    from every location index. The committed bundle's account has `tasks_farmer`
    incomplete, so `tasks_trader` — the ONLY permanent vendor selling anything
    for `tasks_coin` — has no location, `currency_demand` finds no fundable
    vendor, and `CanIAffordTheCurrencyLeaf`'s positive arm is unreachable from
    every scenario. Declaring the achievement is what makes the D9 currency-leaf
    value expressible.

    Validated against the bundle's achievement registry by `from_cache_bundle`,
    which RAISES on a code the capture does not know. Default empty, so every
    scenario written before this keeps the locked world it was pinned in."""
    description: str = ""


@dataclass(frozen=True)
class _CombatTotals:
    """Server-total combat stats for a loadout (value object for
    scenario_state's derive_combat_stats path)."""
    attack: dict[str, int] = field(default_factory=dict)
    dmg: int = 0
    dmg_elements: dict[str, int] = field(default_factory=dict)
    resistance: dict[str, int] = field(default_factory=dict)
    critical_strike: int = 0
    initiative: int = 0
    hp_bonus: int = 0


def _derived_combat_totals(
    equipment: dict[str, str | None], game_data: GameData,
) -> _CombatTotals:
    """Sum of every equipped item's catalog stats: a character's base combat
    stats are zero, so the server's reported totals are exactly the gear sum.
    Utility slots are SKIPPED: boost-family potions fold boost_dmg_*/boost_
    res_*/boost_hp into dmg_elements/resistance/hp_bonus at catalog-build
    time (game_data.py fill), which are combat-time effects the live sheet
    does NOT report as permanent totals — summing them here would repeat the
    zero-stats/hp contamination a third time."""
    attack: dict[str, int] = {}
    dmg = 0
    dmg_elements: dict[str, int] = {}
    resistance: dict[str, int] = {}
    critical_strike = 0
    initiative = 0
    hp_bonus = 0
    for slot, code in equipment.items():
        if code is None or slot.startswith("utility"):
            continue
        stats = game_data.item_stats(code)
        if stats is None:
            raise ValueError(f"derive_combat_stats: no catalog stats for {code!r}")
        for elem in ELEMENTS:
            attack[elem] = attack.get(elem, 0) + stats.attack.get(elem, 0)
            dmg_elements[elem] = (dmg_elements.get(elem, 0)
                                  + stats.dmg_elements.get(elem, 0))
            resistance[elem] = (resistance.get(elem, 0)
                                + stats.resistance.get(elem, 0))
        dmg += stats.dmg
        critical_strike += stats.critical_strike
        initiative += stats.initiative
        hp_bonus += stats.hp_bonus
    return _CombatTotals(
        attack={k: v for k, v in attack.items() if v},
        dmg=dmg,
        dmg_elements={k: v for k, v in dmg_elements.items() if v},
        resistance={k: v for k, v in resistance.items() if v},
        critical_strike=critical_strike,
        initiative=initiative,
        hp_bonus=hp_bonus,
    )


def scenario_state(sc: ScenarioCharacter,
                   game_data: GameData | None = None) -> WorldState:
    equipment: dict[str, str | None] = {slot: None for slot in EQUIPMENT_SLOTS}
    equipment.update(sc.equipment)
    combat = _CombatTotals()
    max_hp = sc.max_hp
    if sc.derive_combat_stats:
        if game_data is None:
            raise ValueError(
                "derive_combat_stats scenarios need game_data at "
                "scenario_state time (gear stats come from the catalog)")
        combat = _derived_combat_totals(equipment, game_data)
        # Server base HP = 115 + 5*level (live-validated against a real
        # character); derived max_hp REPLACES the scenario's hand-declared
        # value under this flag — see ScenarioCharacter.derive_combat_stats.
        max_hp = 115 + 5 * sc.level + combat.hp_bonus
    # Every real character carries all 8 craft/gathering skills starting at
    # level 1 (world_state._fetch_world_state loops SKILL_NAMES with no
    # omissions) — a scenario that only sets the skills it cares about must
    # still produce a state with every key present, or planner code that
    # indexes state.skills[skill] unconditionally (a sound assumption against
    # live data) raises KeyError.
    skills: dict[str, int] = {name: 1 for name in SKILL_NAMES}
    skills.update(sc.skills)
    task_code, task_type, progress, total = sc.task or (None, None, 0, 0)
    return WorldState(
        character=sc.name, level=sc.level, xp=0, max_xp=100,
        hp=sc.hp if sc.hp is not None else max_hp, max_hp=max_hp,
        gold=sc.gold, skills=skills, x=0, y=0,
        inventory=dict(sc.inventory), inventory_max=sc.inventory_max,
        inventory_slots_max=(sc.inventory_slots_max
                             if sc.inventory_slots_max is not None
                             else sc.inventory_max),
        equipment=equipment, cooldown_expires=None,
        task_code=task_code, task_type=task_type,
        task_progress=progress, task_total=total,
        task_lifecycle_phase=derive_task_lifecycle_phase(task_code, progress, total),
        bank_items=dict(sc.bank) if sc.bank is not None else None,
        bank_gold=(sc.bank_gold if sc.bank_gold is not None
                   else (0 if sc.bank is not None else None)),
        bank_capacity=200 if sc.bank is not None else None,
        pending_items=None,
        utility1_slot_quantity=sc.utility_quantities.get("utility1_slot", 0),
        utility2_slot_quantity=sc.utility_quantities.get("utility2_slot", 0),
        active_events={code: FAR_FUTURE for code in sc.active_events},
        raids=[RaidInfo(code=code, name=code, monster=boss, status="active",
                        next_start_at=FAR_FUTURE, remaining_hp=None,
                        total_hp=None, window_ends_at=FAR_FUTURE)
               for code, boss in sc.raids],
        attack=combat.attack,
        dmg=combat.dmg,
        dmg_elements=combat.dmg_elements,
        resistance=combat.resistance,
        critical_strike=combat.critical_strike,
        initiative=combat.initiative,
    )


def load_bundle_game_data(
    path: Path, *, with_ge_orders: bool = False,
    completed_achievements: frozenset[str] = frozenset(),
) -> GameData:
    """The scenario harness's GameData, built from a committed cache bundle.

    `with_ge_orders` forwards to `GameData.from_cache_bundle` and picks which
    MARKET the offline world models: the default quiet book (no standing order
    on anything — the control side of the coverage matrix's GE dimension), or
    the order book captured into the bundle, which is the market the live bot
    plans in. See `from_cache_bundle` for the measurement that made this a
    declared argument rather than a default.

    `completed_achievements` forwards the same way and picks which ACCESS-GATED
    tiles the offline world has open — the capture's account has `tasks_farmer`
    incomplete, which hides the only permanent `tasks_coin` vendor. Again see
    `from_cache_bundle` for the measurement.
    """
    return GameData.from_cache_bundle(
        json.loads(path.read_text()), with_ge_orders=with_ge_orders,
        completed_achievements=completed_achievements)


_COPPER_SET = {
    "weapon_slot": "copper_dagger", "helmet_slot": "copper_helmet",
    "body_armor_slot": "copper_armor", "leg_armor_slot": "copper_legs_armor",
    "boots_slot": "copper_boots", "ring1_slot": "copper_ring",
    "ring2_slot": "copper_ring",
}

_IRON_SET = {
    "weapon_slot": "iron_sword", "helmet_slot": "iron_helm",
    "body_armor_slot": "iron_armor", "leg_armor_slot": "iron_legs_armor",
    "boots_slot": "iron_boots", "ring1_slot": "iron_ring",
    "ring2_slot": "iron_ring", "shield_slot": "iron_shield",
    "amulet_slot": "life_amulet",
}
"""The tier-15 loadout the coverage-matrix cells that are NOT about gear wear.

`_COPPER_SET`'s tier-1 pieces leave a level-20 character losing to most of its
own band, which would put HP_CRITICAL or an unwinnable cascade in front of
whatever the cell is actually testing. This set is deliberately unremarkable —
it exists so a bag-pressure or HP cell varies exactly one dimension."""

_FULL_BANK = {code: 1 for code in (
    "copper_ore", "iron_ore", "coal", "gold_ore", "mithril_ore",
    "copper_bar", "iron_bar", "steel_bar", "gold_bar", "mithril_bar",
    "ash_wood", "spruce_wood", "maple_wood", "dead_wood", "magic_wood",
    "ash_plank", "spruce_plank", "birch_wood", "dead_wood_plank",
    "hardwood_plank", "cowhide", "feather", "wolf_hair", "wolf_bone",
    "pig_skin", "snakeskin", "snake_hide", "lizard_skin", "vermin_leather",
    "yellow_slimeball", "red_slimeball", "blue_slimeball", "green_slimeball",
    "king_slimeball", "sap", "maple_sap", "mushroom", "sunflower",
    "nettle_leaf", "glowstem_leaf", "algae", "gudgeon", "shrimp", "trout",
    "bass", "raw_chicken", "milk_bucket", "egg", "apple", "golden_egg",
)}
"""A bank with NO ROOM: exactly `GameData.bank_capacity` (50, from the committed
bundle's `/my/bank`) distinct codes, so `bank_room.bank_has_room` is False.

The number of DISTINCT codes is what fills a bank — quantities do not — so this
is 50 stacks of one, the cheapest honest way to say "full". Every code is a real
catalogue material a level-20 character would plausibly have banked.

THE 50 IS NOT A MAGIC NUMBER SITTING UNPINNED, and this note is where a reader
finds that out. The literal is hand-listed rather than derived on purpose:
deriving the set to capacity would change WHICH items are banked, which moves
cell 8's behaviour for a reason unrelated to bank pressure. What makes the
coupling loud instead is an EQUALITY against the live capacity, asserted three
ways, all in `tests/test_ai/scenarios/`:

* `test_bag_pressure_cells.test_cell8_bank_is_stocked_to_capacity` —
  `len(state.bank_items) == bundle_game_data.bank_capacity`, so a bundle refresh
  that moves `bank_capacity` in EITHER direction fails here rather than quietly
  handing cell 8 a bank with room;
* `test_bag_pressure_cells.test_cell9_each_axis_silences_exactly_the_guard_it_owns`
  fills cell 9's empty bank from this same set to silence `DEPOSIT_FULL`, so a
  short list stops silencing it;
* `test_scenario_builder.test_registry_item_codes_exist_in_live_catalog` walks
  every scenario's `bank` against the bundle, so a typo'd code — which would
  still COUNT toward 50 — fails too.

Measured: dropping one code from this tuple fails 6 tests across those files."""

def _held_task_cell(name: str, task: tuple[str, str, int, int],
                    description: str) -> ScenarioCharacter:
    """One member of the coverage matrix's HELD-TASK triple (cells 1-3).

    Every field is fixed here so the ONLY thing that differs between the three
    cells is `task`. Built by a function rather than copied three times because
    a controlled triple that drifts apart stops being a control, and three
    hand-maintained literals are exactly how it drifts."""
    return ScenarioCharacter(
        name=name, level=32,
        skills={"mining": 20, "woodcutting": 20, "weaponcrafting": 15,
                "gearcrafting": 15, "jewelrycrafting": 15, "cooking": 10,
                "alchemy": 10, "fishing": 10},
        equipment={
            "weapon_slot": "iron_sword", "helmet_slot": "iron_helm",
            "body_armor_slot": "iron_armor", "leg_armor_slot": "iron_legs_armor",
            "boots_slot": "iron_boots", "ring1_slot": "iron_ring",
            "ring2_slot": "iron_ring", "shield_slot": "iron_shield",
            "amulet_slot": "life_amulet",
        },
        inventory={"iron_ore": 12, "cowhide": 4, "feather": 6},
        inventory_max=140,
        bank={"iron_bar": 6, "cowhide": 8},
        gold=12000,
        derive_combat_stats=True,
        task=task, description=description)


def _ge_market_cell(name: str, *, gearcrafting: int, ge_market: bool,
                    description: str) -> ScenarioCharacter:
    """One member of the coverage matrix's GRAND-EXCHANGE triple (cells 4/5/7).

    The two axes those cells vary are the arguments: `gearcrafting` (D11 — 9 is
    one short of the `feather_coat` rung, 10 is adequate) and `ge_market` (D3).
    Everything else is fixed, which is what makes cell 7 a control rather than
    a fourth unrelated character. `leg_armor_slot` is held a tier behind on
    purpose: it is what makes `iron_legs_armor` the leg target and
    `gearcrafting` the binding skill."""
    return ScenarioCharacter(
        name=name, level=12,
        skills={"mining": 10, "woodcutting": 10, "weaponcrafting": 10,
                "gearcrafting": gearcrafting, "jewelrycrafting": 5,
                "cooking": 5, "alchemy": 5, "fishing": 5},
        equipment={
            "weapon_slot": "iron_sword", "helmet_slot": "iron_helm",
            "body_armor_slot": "iron_armor", "leg_armor_slot": "copper_legs_armor",
            "boots_slot": "iron_boots", "ring1_slot": "iron_ring",
            "ring2_slot": "iron_ring", "shield_slot": "iron_shield",
            "amulet_slot": "life_amulet",
        },
        inventory={"iron_ore": 8, "cowhide": 1},
        inventory_max=130,
        bank={"iron_bar": 3, "cowhide": 2},
        gold=3000,
        derive_combat_stats=True,
        ge_market=ge_market, description=description)


SCENARIOS: dict[str, ScenarioCharacter] = {
    "l1_fresh": ScenarioCharacter(
        name="l1_fresh", level=1, max_hp=120,
        derive_combat_stats=True,  # wave 3a fix-round 1: see the module note
        description="Fresh start: nothing owned — trunk begins, xp branch, starter monster."),
    "l8_overstocked": ScenarioCharacter(
        name="l8_overstocked", level=8, max_hp=200,
        skills={"mining": 5, "woodcutting": 5},
        equipment=dict(_COPPER_SET),
        inventory={"feather": 90, "raw_chicken": 6}, inventory_max=100,
        description="96/100 bag of loot — the deposit guard must preempt."),
    "l10_copper_adequate": ScenarioCharacter(
        name="l10_copper_adequate", level=10, max_hp=240,
        skills={"mining": 10, "woodcutting": 10, "weaponcrafting": 10,
                "gearcrafting": 10, "alchemy": 5},
        equipment=dict(_COPPER_SET),
        bank={"sunflower": 20},
        derive_combat_stats=True,  # wave 3a fix-round 1: see the module note
        # HELD TASK, value "unwinnable and NO gear closes the gap" (measured:
        # has_combat_deficit True, deficit_upgrade_target None). A dryad is far
        # out of this build's band, so the deficit walk runs to exhaustion and
        # names nothing -- the fall-through arm of `deficit_upgrade_target`,
        # which had no offline witness at all. IN_PROGRESS rather than 0/10 so
        # the phase is distinct from ACCEPTED; measured not to move this
        # scenario's chosen root/step/goal/first action.
        task=("dryad", "monsters", 4, 10),
        description="Band-adequate copper set, empty utility slots, potion mats banked. "
                    "Holds an unwinnable dryad task no gear upgrade can close."),
    "l10_weapon_upgrade": ScenarioCharacter(
        name="l10_weapon_upgrade", level=10, max_hp=240,
        skills={"mining": 10, "weaponcrafting": 10},
        equipment={**_COPPER_SET, "weapon_slot": "wooden_stick"},
        bank={"iron_ore": 60, "copper_ore": 20},
        derive_combat_stats=True,  # wave 3a fix-round 1: see the module note
        description="Weapon slot lags a tier; upgrade mats banked — gear branch."),
    "l3_low_hp": ScenarioCharacter(
        name="l3_low_hp", level=3, hp=20, max_hp=80,
        description="Critical HP — the survival guard preempts every branch."),
    "l12_taskgated_bag": ScenarioCharacter(
        name="l12_taskgated_bag", level=12, max_hp=260,
        skills={"gearcrafting": 10},
        equipment=dict(_COPPER_SET),
        bank={"cowhide": 5, "feather": 2},
        derive_combat_stats=True,  # wave 3a fix-round 1: see the module note
        description="Satchel mats banked, 0 tasks_coin — the task-funding chain."),

    # --- Per-band trunk liveness net (docs/superpowers/specs/
    # 2026-07-06-progression-tree-design.md Phase 1, deferred to this pass):
    # one scenario per trunk band, each a plausible character ENTERING that
    # band slightly under-tier — the gear branch always has a reachable
    # target (so band_adequate is False: has_structural_upgrade is true in
    # every one of these), while the xp/trunk branch survives as a
    # decide_tree fallback. See tests/test_ai/scenarios/test_band_liveness.py.
    "l15_midband": ScenarioCharacter(
        name="l15_midband", level=15, max_hp=300, gold=50,
        skills={"mining": 12, "woodcutting": 12, "weaponcrafting": 10,
                "gearcrafting": 10, "fishing": 10, "cooking": 10,
                "alchemy": 6, "jewelrycrafting": 6},
        equipment={
            "weapon_slot": "iron_dagger", "helmet_slot": "iron_helm",
            "body_armor_slot": "iron_armor", "leg_armor_slot": "iron_legs_armor",
            "boots_slot": "iron_boots", "ring1_slot": "iron_ring",
            "shield_slot": "iron_shield",
        },
        bank={"iron_ore": 15, "spruce_wood": 10, "feather": 5, "wolf_bone": 3},
        inventory_max=120,
        description="Mid L10-20 band: full iron (L10) set, L15 upgrades on offer."),
    "l20_band_entry": ScenarioCharacter(
        name="l20_band_entry", level=20, max_hp=360, gold=100,
        skills={"mining": 18, "woodcutting": 18, "weaponcrafting": 15,
                "gearcrafting": 15, "fishing": 15, "cooking": 15,
                "alchemy": 10, "jewelrycrafting": 10},
        equipment={
            "weapon_slot": "highwayman_dagger", "helmet_slot": "lucky_wizard_hat",
            "body_armor_slot": "mushmush_jacket", "leg_armor_slot": "adventurer_pants",
            "boots_slot": "adventurer_boots", "ring1_slot": "air_ring",
            "amulet_slot": "wisdom_amulet",
        },
        bank={"coal": 10, "wolf_bone": 5, "wolf_hair": 5, "green_cloth": 5},
        inventory_max=130,
        description="Entering L20-30 band: L15 gear, L20 upgrades on offer."),
    "l30_band_entry": ScenarioCharacter(
        name="l30_band_entry", level=30, max_hp=480, gold=200,
        skills={"mining": 28, "woodcutting": 28, "weaponcrafting": 25,
                "gearcrafting": 25, "fishing": 25, "cooking": 25,
                "alchemy": 18, "jewelrycrafting": 18},
        equipment={
            "weapon_slot": "dreadful_staff", "helmet_slot": "piggy_helmet",
            "body_armor_slot": "bandit_armor", "leg_armor_slot": "piggy_pants",
            "boots_slot": "hard_leather_boots", "ring1_slot": "ring_of_the_adept",
            "amulet_slot": "emerald_amulet",
        },
        bank={"gold_ore": 15, "sap": 5, "red_cloth": 5},
        inventory_max=140,
        description="Entering L30-40 band: L25 gear (L20 boots — no L25 boots "
                     "exist in the catalog), L30 upgrades on offer."),
    "l40_band_entry": ScenarioCharacter(
        name="l40_band_entry", level=40, max_hp=600, gold=400,
        skills={"mining": 38, "woodcutting": 38, "weaponcrafting": 35,
                "gearcrafting": 35, "fishing": 35, "cooking": 35,
                "alchemy": 25, "jewelrycrafting": 25},
        equipment={
            "weapon_slot": "cursed_sceptre", "helmet_slot": "strangold_helmet",
            "body_armor_slot": "strangold_armor", "leg_armor_slot": "strangold_legs_armor",
            "boots_slot": "enchanter_boots", "ring1_slot": "malefic_ring",
            "amulet_slot": "corrupted_stone_amulet",
        },
        bank={"mithril_ore": 10, "magic_wood": 5},
        inventory_max=150,
        description="Entering L40-50 band: L35 gear, L40 upgrades on offer."),
    "l48_capstone_approach": ScenarioCharacter(
        name="l48_capstone_approach", level=48, max_hp=690, gold=800,
        skills={"mining": 46, "woodcutting": 46, "weaponcrafting": 42,
                "gearcrafting": 42, "fishing": 42, "cooking": 42,
                "alchemy": 35, "jewelrycrafting": 35},
        equipment={
            "weapon_slot": "mithril_sword", "helmet_slot": "mithril_helm",
            "body_armor_slot": "mithril_platebody", "leg_armor_slot": "mithril_platelegs",
            "boots_slot": "mithril_boots", "ring1_slot": "mithril_ring",
            "amulet_slot": "greater_sapphire_amulet",
        },
        bank={"adamantite_ore": 5, "mithril_ore": 10},
        inventory_max=150,
        description="Approaching the L50 capstone: L40 gear, L45 upgrades on "
                     "offer — empirical capstone-reachability evidence."),

    # --- Band-ADEQUATE capstone counterpart (2026-07-07 fix wave, per
    # tests/test_ai/scenarios/test_band_liveness.py): l48_capstone_approach
    # above is deliberately under-tier so the gear branch always has a
    # target; this scenario is the opposite construction — every slot
    # already holds the catalog-best is_attainable_now item (empirically
    # fixed-point-iterated against near_term_gear: mithril tier for the
    # already-filled slots, plus wooden_shield/copper_ring filling the
    # previously-empty shield/ring2 slots — no further near_term_gear
    # candidate exists), and BOTH utility slots are stocked with the real
    # bootstrap_potion_target (health_splash_potion) at positive quantity so
    # equipped_potion_qty > 0 excludes the utility candidate too. This
    # forces has_structural_upgrade False by construction — the XP/capstone
    # branch path the per-band net had no scenario for. rune slot is left
    # empty deliberately: near_term_gear emits no candidate for it from this
    # state either (verified empirically). ARTIFACT slots stock perfect_pearl
    # (RE-DERIVED 2026-07-07 GAP-2 fix — objective._gatherable now reads the
    # FULL drop set, so small_pearls, a rare fishing-spot drop, opens
    # perfect_pearl's archaeologist-vendor route as attainable-now at ANY
    # level ≥ 19; left unequipped this scenario was no longer a fixed point,
    # perfect_pearl (equip_value 201, all prospecting) became a real
    # near_term_gear candidate and has_structural_upgrade flipped True).
    # Stocking it (duplicate-fill artifact type, same item all 3 slots)
    # restores the "no structural candidate" invariant this scenario exists
    # to provide — see tests/test_ai/scenarios/test_slot_coverage.py's GAP-2
    # note for the un-restocked witness (l35_artifact_fill).
    "l48_band_adequate": ScenarioCharacter(
        name="l48_band_adequate", level=48, max_hp=690, gold=800,
        skills={"mining": 46, "woodcutting": 46, "weaponcrafting": 42,
                "gearcrafting": 42, "fishing": 42, "cooking": 42,
                "alchemy": 35, "jewelrycrafting": 35},
        equipment={
            "weapon_slot": "mithril_sword", "helmet_slot": "mithril_helm",
            "body_armor_slot": "mithril_platebody", "leg_armor_slot": "mithril_platelegs",
            "boots_slot": "mithril_boots", "ring1_slot": "mithril_ring",
            "ring2_slot": "copper_ring", "amulet_slot": "greater_sapphire_amulet",
            "shield_slot": "wooden_shield",
            "artifact1_slot": "perfect_pearl", "artifact2_slot": "perfect_pearl",
            "artifact3_slot": "perfect_pearl",
            "utility1_slot": "health_splash_potion", "utility2_slot": "health_splash_potion",
        },
        utility_quantities={"utility1_slot": 20, "utility2_slot": 20},
        bank={"adamantite_ore": 5, "mithril_ore": 10},
        inventory_max=150,
        description="Band-ADEQUATE at L48: every slot already holds the "
                     "best is_attainable_now item, no structural or utility "
                     "gear candidate exists — the XP/capstone branch, not "
                     "the gear branch."),

    "l48_raid_active": ScenarioCharacter(
        name="l48_raid_active", level=48, max_hp=690, gold=800,
        skills={"mining": 46, "woodcutting": 46, "weaponcrafting": 42,
                "gearcrafting": 42, "fishing": 42, "cooking": 42,
                "alchemy": 35, "jewelrycrafting": 35},
        equipment={
            "weapon_slot": "mithril_sword", "helmet_slot": "mithril_helm",
            "body_armor_slot": "mithril_platebody", "leg_armor_slot": "mithril_platelegs",
            "boots_slot": "mithril_boots", "ring1_slot": "mithril_ring",
            "ring2_slot": "copper_ring", "amulet_slot": "greater_sapphire_amulet",
            "shield_slot": "wooden_shield",
            "artifact1_slot": "perfect_pearl", "artifact2_slot": "perfect_pearl",
            "artifact3_slot": "perfect_pearl",
            "utility1_slot": "health_splash_potion", "utility2_slot": "health_splash_potion",
        },
        utility_quantities={"utility1_slot": 20, "utility2_slot": 20},
        bank={"adamantite_ore": 5, "mithril_ore": 10},
        inventory_max=150,
        raids=(("enchanted_fairy", "pixie"),),
        description="l48_band_adequate WITH an active raid. The POSITIVE pole "
                     "of the L48 wall pair: byte-identical state except that a "
                     "raid window is open. enchanted_fairy's boss (pixie, L40) "
                     "sits on the OVERWORLD at (-4,10), so it needs no layer "
                     "transition and clears the level+2 suicide cap at L48 — "
                     "unlike god_of_the_sun (sonnengott L55, underground). "
                     "Deliberately does NOT set derive_combat_stats: that alone "
                     "unlocks unrelated work (the pair first planned "
                     "Gather(gold_rocks), not the boss), which would let the "
                     "positive pole pass for a reason that has nothing to do "
                     "with raids."),

    # --- Event-gear pursuit across the L48 wall (2026-07-07 slot-coverage
    # pass): the l48_band_adequate loadout with REAL combat stats
    # (derive_combat_stats — the zero-stat harness default makes every
    # monster unwinnable, so event-gated attainability could never open)
    # and the corrupted_ogre event up. With the event active the L20 ogre
    # (winnable at this loadout) drops corrupted_gem, the permanent
    # cultist_wizard sells corrupted_crown/corrupted_skull for
    # corrupted_gem, and near_term_gear gains an event-only candidate at
    # helmet_slot (corrupted_crown). RE-DERIVED 2026-07-07 GAP-2 fix:
    # artifact1_slot/artifact3_slot are no longer event-exclusive,
    # perfect_pearl duplicate-fills them regardless of the event once
    # objective._gatherable opens the small_pearls rare-drop route.
    # RE-DERIVED AGAIN 2026-07-08 (Task 2, duplicate-slot-best-fill fix):
    # artifact2_slot is no longer event-exclusive EITHER — corrupted_skull
    # (value 17) never outranks a 2nd copy of perfect_pearl (value 201),
    # dup-allowed slots always duplicate-fill the single best item now, so
    # helmet_slot is the event's ONLY remaining candidate-surface delta; see
    # test_slot_coverage.py's EVENT_ONLY_CANDIDATES docstring. Artifact
    # slots are deliberately left UNSTOCKED here (unlike l48_band_adequate/
    # l30_rune_fill/l20_dual_utility) — perfect_pearl duplicate-filling them
    # is itself part of the observed WITHOUT-event candidate set. Without
    # the event the same monsters have no known spawn, the currency leaf
    # stays closed, and (with real stats) the shield/ring2/boots/bag slots
    # also open non-event candidates — so the event-attribution tests
    # compare the WITH/WITHOUT candidate sets on this same state, and the
    # Wait isolation witness stays l48_band_adequate (zero-stat, untouched).
    "l48_event_active": ScenarioCharacter(
        name="l48_event_active", level=48, gold=800,
        skills={"mining": 46, "woodcutting": 46, "weaponcrafting": 42,
                "gearcrafting": 42, "fishing": 42, "cooking": 42,
                "alchemy": 35, "jewelrycrafting": 35},
        equipment={
            "weapon_slot": "mithril_sword", "helmet_slot": "mithril_helm",
            "body_armor_slot": "mithril_platebody", "leg_armor_slot": "mithril_platelegs",
            "boots_slot": "mithril_boots", "ring1_slot": "mithril_ring",
            # ring2 RE-DERIVED 2026-08-04 (dmg_elements hoist, the equip-loop
            # fix): a level-1 copper_ring on a level-48 mithril-clad character
            # was a fixture artifact, and once combat_raw prices mithril_helm's
            # 40 points of element damage % the crown's gain over that helm
            # (50030) falls BELOW royal_skeleton_ring's gain over the
            # copper_ring (80030) — a NON-event root would have taken the head
            # of the ranking and this scenario would stop isolating the event
            # seam it exists for. Rings are duplicate-allowed, so a 2nd
            # mithril_ring is the honest fixed point for ring2.
            "ring2_slot": "mithril_ring", "amulet_slot": "greater_sapphire_amulet",
            "shield_slot": "wooden_shield",
            "utility1_slot": "health_splash_potion", "utility2_slot": "health_splash_potion",
        },
        utility_quantities={"utility1_slot": 20, "utility2_slot": 20},
        bank={"adamantite_ore": 5, "mithril_ore": 10},
        inventory_max=150,
        active_events=("corrupted_ogre",),
        derive_combat_stats=True,
        description="L48 with real mithril combat stats and the "
                     "corrupted_ogre event live — event-sourced gear "
                     "(corrupted_crown/corrupted_skull via corrupted_gem) "
                     "must enter the candidate surface."),

    # --- Bag-slot pursuit (2026-07-07 slot-coverage pass, deliverable 2;
    # RE-DERIVED 2026-07-07 hp-derivation fix wave — see report). L10 in the
    # best L10-tier loadout (full iron + life_amulet), bag_slot EMPTY, and
    # the bank holding the satchel recipe's full monster-drop inputs
    # (cowhide 5/5 + feather 2/2 — only the task-funded jasper_crystal
    # missing, 0 tasks_coin held). At the CORRECTED max_hp formula (115 +
    # 5*level + gear hp, 375 here) cow IS winnable and the satchel chain IS
    # live — the original "invisible at L10" framing relied on the
    # harness's hand-declared max_hp (240) undershooting reality and is
    # retired (GAP-1 is now pinned directly, scenario-independent, by
    # test_bag_slot_banked_stock_not_credited). The ACTUAL L10 behavior:
    # iron_armor is ALSO not yet a fixed point, so adventurer_vest
    # (craftable from the same banked cowhide) is a competing near_term_gear
    # candidate that outranks bag_slot outright — satchel survives only as
    # a fallback root. See test_l10_bag_pursuit_satchel_live_but_vest_outranks.
    "l10_bag_pursuit": ScenarioCharacter(
        name="l10_bag_pursuit", level=10,
        skills={"mining": 10, "woodcutting": 10, "weaponcrafting": 10,
                "gearcrafting": 10, "alchemy": 5},
        equipment={
            # RE-FIXED-POINT 2026-08-04 (pursuit_value unification):
            # `near_term_gear` ranks on `pursuit_value`, whose combat term is
            # now the ONE gear ruler's own. Slots that were a fixed point only
            # for the retired flat `combat_raw` sum are re-converged here, so
            # this scenario keeps isolating the gap it was built for instead of
            # leaking unrelated candidates into the ranking.
            "weapon_slot": "greater_wooden_staff", "helmet_slot": "adventurer_helmet",
            "body_armor_slot": "adventurer_vest", "leg_armor_slot": "iron_legs_armor",
            "boots_slot": "iron_boots", "ring1_slot": "iron_ring",
            "ring2_slot": "iron_ring", "shield_slot": "iron_shield",
            "amulet_slot": "air_and_water_amulet",
            "utility1_slot": "small_health_potion", "utility2_slot": "small_health_potion",
        },
        utility_quantities={"utility1_slot": 20, "utility2_slot": 20},
        bank={"cowhide": 5, "feather": 2},
        derive_combat_stats=True,
        description="L10, bag_slot empty, satchel mats banked bar the "
                     "task-funded jasper_crystal — at real hp the chain is "
                     "LIVE but a competing body-armor upgrade (same banked "
                     "cowhide) outranks it; satchel survives as fallback."),
    # The witness that ISOLATES the satchel chain: +2 levels (matches the
    # original "minimal delta" framing) PLUS every other slot pushed to its
    # own near_term_gear fixed point (RE-DERIVED 2026-07-07 hp-derivation fix
    # wave: at corrected hp the old loadout was no longer a fixed point
    # either — adventurer_helmet/forest_ring opened as new candidates and
    # out-ranked the bag entirely, same competing-candidate effect as
    # l10_bag_pursuit above). With every slot but bag_slot already at its
    # argmax, near_term_gear covers bag_slot -> satchel as the SOLE
    # candidate and the full stack runs the task-funding chain
    # (ReachCurrency(tasks_coin, 8) -> AcceptTask/Fight/CompleteTask) toward
    # the jasper_crystal buy.
    "l12_bag_pursuit": ScenarioCharacter(
        name="l12_bag_pursuit", level=12,
        skills={"mining": 10, "woodcutting": 10, "weaponcrafting": 10,
                "gearcrafting": 10, "alchemy": 5},
        equipment={
            # helmet/body RE-FIXED-POINT 2026-08-04 (dmg_elements hoist, the
            # equip-loop fix): the adventurer pieces bought their extra wisdom
            # with element damage % that combat_raw could not see, so they
            # LOOKED like the L12 argmax. Now that the hoist prices dmg_<elem>
            # exactly as armor_score already did, iron_armor (cr 70) and
            # iron_helm (cr 58) outrank adventurer_vest (cr 66) and
            # adventurer_helmet (cr 55) — the same verdict 170ed8d8 reached on
            # the monster-relative side. Equipping the true argmax keeps every
            # non-bag slot at its fixed point, which is this scenario's whole
            # isolation methodology.
            # RE-FIXED-POINT 2026-08-04 (pursuit_value unification):
            # `near_term_gear` ranks on `pursuit_value`, whose combat term is
            # now the ONE gear ruler's own. Slots that were a fixed point only
            # for the retired flat `combat_raw` sum are re-converged here, so
            # this scenario keeps isolating the gap it was built for instead of
            # leaking unrelated candidates into the ranking.
            "weapon_slot": "greater_wooden_staff", "helmet_slot": "adventurer_helmet",
            "body_armor_slot": "adventurer_vest", "leg_armor_slot": "iron_legs_armor",
            "boots_slot": "iron_boots", "ring1_slot": "iron_ring",
            # ring2 RE-DERIVED (Task 2, GAP-2 review, 2026-07-08): rings are
            # duplicate-allowed, so near_term_gear's true fixed point is BOTH
            # ring slots holding the single best attainable-now ring
            # (forest_ring) — a distinct, weaker 2nd ring (iron_ring) is no
            # longer a fixed point once _slot_assignments duplicates the
            # best instead of ranking distinct items into each slot.
            "ring2_slot": "iron_ring", "shield_slot": "iron_shield",
            "amulet_slot": "air_and_water_amulet",
            "utility1_slot": "small_health_potion", "utility2_slot": "small_health_potion",
        },
        utility_quantities={"utility1_slot": 20, "utility2_slot": 20},
        bank={"cowhide": 5, "feather": 2},
        derive_combat_stats=True,
        description="L12 twin of l10_bag_pursuit: cow winnable, every other "
                     "slot at its own near_term_gear fixed point (iron armor, "
                     "iron helm, both rings) — satchel is the sole remaining "
                     "candidate and the task-funding chain fires."),

    # --- Artifact slots (deliverable 3). L35, plausible combat loadout
    # (l30_band_entry gear + slime_shield/satchel, both rings filled),
    # artifact1/2/3_slot ALL empty, utilities stocked with the bootstrap
    # target so no utility candidate fires. GAP-2 FIXED 2026-07-07:
    # objective._gatherable now reads the FULL drop set, so small_pearls (a
    # rare fishing-spot drop) is gatherable and perfect_pearl's
    # archaeologist-vendor route opens — the tree NOW targets all three
    # artifact slots (perfect_pearl, duplicate-filled) as the argmax
    # candidate. Every other artifact in the bundle stays closed at this
    # tier for its own, unrelated reason (lich/rosenblood/cultist_emperor
    # unwinnable; corrupted_gem event-monster-only; novice_guide has no
    # acquisition path at all) — see test_slot_coverage.py's
    # test_l35_artifact_perfect_pearl_targeted_others_closed.
    # GAP-7 FIXED 2026-07-08: recipe_closure now unions the secondary-drop
    # layers into needed_resources, so GatherMaterials(small_pearls) admits
    # the factory's targeted secondary-drop gather and PLANS
    # (Gather(bass_spot->small_pearls); fishing 30 covers trout_spot 20 /
    # bass_spot 30). No demotion any more — the GAP-6 drop-farm story
    # (Fight(spider) -> Equip(old_boots)) moved to the pearl-stocked
    # variant l35_boots_drop_farm below. See test_slot_coverage.py:
    # test_l35_artifact_fill_pearl_route_plans.
    "l35_artifact_fill": ScenarioCharacter(
        name="l35_artifact_fill", level=35, gold=300,
        skills={"mining": 32, "woodcutting": 32, "weaponcrafting": 30,
                "gearcrafting": 30, "fishing": 30, "cooking": 30,
                "alchemy": 20, "jewelrycrafting": 20},
        equipment={
            # weapon/boots RE-FIXED-POINT 2026-07-08 (Task-3 pursuit_value):
            # combat-dominant pursuit_value ranks wooden_club (combat_raw 71)
            # over the equipped dreadful_staff (55) and snakeskin_boots (96)
            # over hard_leather_boots (49, whose +50 prospecting flat
            # equip_value over-credited) — those were structural candidates
            # masking the artifact slots. Equipping the true combat argmax in
            # each restores the "artifact slots the SOLE target" design.
            "weapon_slot": "wooden_club", "helmet_slot": "piggy_helmet",
            "body_armor_slot": "bandit_armor", "leg_armor_slot": "piggy_pants",
            "boots_slot": "snakeskin_boots",
            # RE-FIXED-POINT 2026-08-04 (pursuit_value unification):
            # `near_term_gear` ranks on `pursuit_value`, whose combat term is
            # now the ONE gear ruler's own, so slots that were a fixed point
            # only for the retired flat `combat_raw` sum are re-converged here.
            # Without this the scenario leaks unrelated candidates into the
            # ranking and stops isolating the gap it was built for.
            "ring1_slot": "gold_ring",
            "ring2_slot": "gold_ring", "amulet_slot": "emerald_amulet",
            "shield_slot": "slime_shield", "bag_slot": "satchel",
            "utility1_slot": "minor_health_potion", "utility2_slot": "minor_health_potion",
        },
        utility_quantities={"utility1_slot": 15, "utility2_slot": 15},
        bank={"gold_ore": 10},
        derive_combat_stats=True,
        description="L35 combat loadout, all three artifact slots empty — "
                     "RE-DERIVED 2026-07-08 (GAP-7 fixed): perfect_pearl "
                     "(small_pearls rare-fishing-drop route) is still the "
                     "argmax artifact target and its step now PLANS: "
                     "recipe_closure reads the full drop set, so the "
                     "secondary-drop fishing gather is admitted and the "
                     "cycle gathers pearls instead of Waiting/demoting."),

    # --- GAP-6 coverage keeper (2026-07-08, split out by the GAP-7 fix):
    # l35_artifact_fill with the three artifact slots STOCKED
    # (perfect_pearl x3 — prospecting-only, combat stats unchanged), so the
    # pearl route is already done and the boots upgrade is the live gear
    # target. Preserves the drop-farm story the GAP-7 flip would otherwise
    # have erased from the net: old_boots (recipe-less, non-purchasable,
    # pure monster-drop) routes through UpgradeEquipmentGoal, whose
    # relevant_actions emits the sole winnable dropper spider (L20 — grey
    # at L35, xp_per_kill == 0) as the drop_farm Fight plus the synthesized
    # Equip leg. Pinned by test_slot_coverage.py's
    # test_l35_boots_drop_farm_fights_grey_dropper.
    "l35_boots_drop_farm": ScenarioCharacter(
        name="l35_boots_drop_farm", level=35, gold=300,
        skills={"mining": 32, "woodcutting": 32, "weaponcrafting": 30,
                "gearcrafting": 30, "fishing": 30, "cooking": 30,
                "alchemy": 20, "jewelrycrafting": 20},
        equipment={
            # RE-DERIVED 2026-07-08 (Task-3 pursuit_value): the GAP-6 drop-farm
            # target was old_boots (a pure-drop boots), but combat-dominant
            # pursuit_value correctly ranks the craftable snakeskin_boots
            # (combat_raw 96) above old_boots (90), so old_boots can no longer
            # be a boots argmax. The GAP-6 mechanism (drop-farm a recipe-less,
            # pure monster-drop equip target) is preserved with a target that
            # IS an argmax under pursuit_value: wooden_club (weapon, recipe-less,
            # combat_raw 71, dropped by the grey L20 ogre). snakeskin_boots is
            # equipped here (fills boots at its combat argmax) so wooden_club is
            # the SOLE remaining gear candidate and the drop-farm story isolates
            # cleanly. weapon_slot deliberately stays dreadful_staff (55 < 71) so
            # wooden_club remains a live pursuit_value upgrade.
            #
            # SUPERSEDED 2026-07-15 (weapon-winnability guard): wooden_club is
            # marginal-0 at L35 (unlocks no monster the loadout cannot already
            # beat), so the guard suppresses it as an ARBITER target and
            # chosen_root falls to ReachCharLevel. The pursuit_value ranking
            # above still holds; the guard is a later, orthogonal targeting gate.
            # This scenario now backs the drop-farm MECHANISM test with the goal
            # PINNED to wooden_club (see test_l35_boots_drop_farm_fights_grey_
            # dropper), not an arbiter-level chosen_root assertion.
            "weapon_slot": "dreadful_staff", "helmet_slot": "piggy_helmet",
            "body_armor_slot": "bandit_armor", "leg_armor_slot": "piggy_pants",
            "boots_slot": "snakeskin_boots",
            # RE-FIXED-POINT 2026-08-04 (pursuit_value unification):
            # `near_term_gear` ranks on `pursuit_value`, whose combat term is
            # now the ONE gear ruler's own, so slots that were a fixed point
            # only for the retired flat `combat_raw` sum are re-converged here.
            "ring1_slot": "gold_ring",
            "ring2_slot": "gold_ring", "amulet_slot": "emerald_amulet",
            "shield_slot": "slime_shield", "bag_slot": "satchel",
            "artifact1_slot": "perfect_pearl", "artifact2_slot": "perfect_pearl",
            "artifact3_slot": "perfect_pearl",
            "utility1_slot": "minor_health_potion", "utility2_slot": "minor_health_potion",
        },
        utility_quantities={"utility1_slot": 15, "utility2_slot": 15},
        bank={"gold_ore": 10},
        derive_combat_stats=True,
        description="l35 loadout, artifacts pearl-stocked, boots filled at "
                     "the combat argmax (snakeskin_boots). State fixture for the "
                     "GAP-6 drop-farm MECHANISM: UpgradeEquipmentGoal pinned to "
                     "the pure-drop wooden_club (weapon) emits + plans its grey "
                     "dropper ogre — Fight(ogre) -> Equip. NB (2026-07-15): the "
                     "weapon-winnability guard now suppresses wooden_club at the "
                     "ARBITER level (marginal 0 at L35), so chosen_root is no "
                     "longer wooden_club; the mechanism is covered with the goal "
                     "pinned. See test_l35_boots_drop_farm_fights_grey_dropper."),

    # --- Rune slot (deliverable 4). L30 at the near_term_gear fixed point
    # for every other slot (the equip_value argmax set — utility-stat gear
    # included, that IS what the metric converges to), rune_slot EMPTY,
    # alchemy 25 so the stocked minor_health_potion is also the bootstrap
    # target (no utility candidate), and 25000 gold ≥ the 20000
    # lifesteal_rune price at the permanent rune_vendor — the rune IS
    # attainable-now via the gold-purchase leaf and near_term_gear covers
    # rune_slot. GAP-3 FIXED 2026-07-08: the chain is LIVE end to end —
    # objective_step_goal routes the recipe-less gold-vendor rune to
    # GatherMaterials(lifesteal_rune), whose is_plannable now credits
    # state.gold (analyze_currency_leaves' gold arm; gold is not an
    # inventory item), and the search finds the one-step
    # NpcBuy(lifesteal_rune x1 @rune_vendor) plan (movement folds into the
    # buy's apply; the equip is the next stepwise cycle's leg).
    # ARTIFACT slots stock perfect_pearl (RE-DERIVED 2026-07-07 GAP-2 fix —
    # see l48_band_adequate's comment for the mechanism: perfect_pearl became
    # a real near_term_gear candidate at any level >= 19 once
    # objective._gatherable started reading the full drop set). Restocked so
    # the rune slot stays the SOLE isolated target, per this scenario's
    # documented "every other slot at its own fixed point" methodology.
    "l30_rune_fill": ScenarioCharacter(
        name="l30_rune_fill", level=30, gold=25000,
        # bank_gold RE-DERIVED (Task 3, gold-reserve discipline, 2026-07-08):
        # the gold arm now also clears `progression_reserve.reserve_floor`,
        # which at this loadout is 50000 (dedup'd for the rune leaf itself —
        # the OTHER near-term gold target is `backpack`@50000 for bag_slot,
        # unrelated to the rune). Affordability needs pocket+bank >= price
        # (20000) + reserve (50000) = 70000. Pocket stays 25000 so
        # near_term_gear/is_attainable_now (POCKET-gold-only, unaffected by
        # the reserve) does NOT also see 70000 pocket gold and admit backpack
        # as a second candidate — the extra 50000 is ferried through KNOWN
        # bank gold instead (analyze_currency_leaves reads pocket+bank),
        # leaving this scenario's single-target isolation intact. 25000 +
        # 50000 = 75000 >= 70000, a 5000 margin.
        skills={"mining": 28, "woodcutting": 28, "weaponcrafting": 25,
                "gearcrafting": 25, "fishing": 25, "cooking": 25,
                "alchemy": 25, "jewelrycrafting": 18},
        equipment={
            # helmet/boots/amulet RE-FIXED-POINT 2026-07-08 (Task-3
            # pursuit_value): the old efficiency picks (wolf_ears helmet,
            # hard_leather_boots [+50 prospecting], wisdom_amulet [+60 wisdom])
            # are outranked under combat-dominant pursuit_value by the combat
            # argmax in each slot (hard_leather_helmet cr93, adventurer_boots,
            # emerald_amulet cr70) — those combat upgrades were masking the
            # rune. Equipping the true argmax in each restores the "every other
            # slot at its own fixed point, rune_slot the SOLE target" design.
            # helmet RE-FIXED-POINT AGAIN 2026-08-04 (dmg_elements hoist, the
            # equip-loop fix): hard_leather_helmet (cr 93, all resistance) is no
            # longer the L30 helmet argmax now that combat_raw prices
            # per-element damage % the way armor_score already did —
            # skeleton_helmet (cr 106) outranks it and was masking the rune
            # again. Equipping the true argmax restores this scenario's "every
            # other slot at its own fixed point, rune_slot the SOLE target".
            # RE-FIXED-POINT 2026-08-04 (pursuit_value unification):
            # `near_term_gear` ranks on `pursuit_value`, whose combat term is
            # now the ONE gear ruler's own, so slots that were a fixed point
            # only for the retired flat `combat_raw` sum are re-converged here.
            "weapon_slot": "battlestaff", "helmet_slot": "lucky_wizard_hat",
            "body_armor_slot": "bandit_armor", "leg_armor_slot": "piggy_pants",
            "boots_slot": "snakeskin_boots", "ring1_slot": "gold_ring",
            # ring2 RE-DERIVED (Task 2, GAP-2 review, 2026-07-08): rings are
            # duplicate-allowed. ring_of_the_adept (ring1) is not itself
            # attainable-now at this loadout (already owned, not currently
            # acquirable), so it isn't a candidate; among attainable-now
            # rings, life_ring is the argmax and near_term_gear's true fixed
            # point for ring2 is a 2nd life_ring, not the weaker forest_ring
            # a distinct-ranked-fill used to leave in place.
            "ring2_slot": "gold_ring", "amulet_slot": "emerald_amulet",
            "shield_slot": "iron_shield", "bag_slot": "satchel",
            "artifact1_slot": "perfect_pearl", "artifact2_slot": "perfect_pearl",
            "artifact3_slot": "perfect_pearl",
            "utility1_slot": "minor_health_potion", "utility2_slot": "minor_health_potion",
        },
        utility_quantities={"utility1_slot": 15, "utility2_slot": 15},
        bank={"gold_ore": 5}, bank_gold=50000,
        derive_combat_stats=True,
        description="L30, rune_slot empty, 25000 pocket gold + 50000 bank "
                     "gold for the 20000 lifesteal_rune (permanent "
                     "rune_vendor) plus its 50000 progression-reserve floor "
                     "(Task 3, 2026-07-08) — the tree arms the rune root and "
                     "the gold buy chain plans NpcBuy (GAP-3 fixed "
                     "2026-07-08; reserve-cleared 2026-07-08)."),

    # --- Utility slots, both empty (deliverable 5; RE-DERIVED 2026-07-07
    # hp-derivation fix wave — see report). L20 at the near_term_gear
    # structural fixed point (no slot upgrade exists), alchemy 20
    # (minor_health_potion is the bootstrap target) with its mats banked
    # (nettle_leaf + algae), BOTH utility slots empty. At the corrected max_hp
    # formula (530 on this loadout, vs the old hand-declared 360) the old loadout was
    # no longer a fixed point: wolf_ears/mushmush_bow opened as new
    # near_term_gear candidates (their droppers become winnable at the real
    # hp) and outranked the XP branch outright — re-iterated to a fixed
    # point under real stats (helmet_slot -> wolf_ears, weapon_slot ->
    # mushmush_bow) to restore the scenario's design intent: no structural
    # gear candidate at all. LIMITATION (pinned): the band reads adequate
    # (winnable monster + no structural upgrade — empty utility slots
    # deliberately DON'T count, per has_structural_upgrade), so the XP
    # branch outranks the utility fill: the first decision is the trunk
    # grind, and ObtainItem(minor_health_potion, utility1_slot) survives
    # only as a fallback root.
    # ARTIFACT slots stock perfect_pearl (RE-DERIVED 2026-07-07 GAP-2 fix —
    # see l48_band_adequate's comment for the mechanism). Restocked so the
    # XP-vs-utility comparison this scenario exists for stays isolated from
    # the unrelated artifact-slot candidate GAP-2 opened.
    "l20_dual_utility": ScenarioCharacter(
        name="l20_dual_utility", level=20, gold=100,
        skills={"mining": 18, "woodcutting": 18, "weaponcrafting": 15,
                "gearcrafting": 15, "fishing": 15, "cooking": 15,
                "alchemy": 20, "jewelrycrafting": 10},
        equipment={
            # helmet/body RE-FIXED-POINT 2026-07-08 (Task-3 pursuit_value):
            # under combat-dominant pursuit_value the old efficiency helmet
            # (wolf_ears, +50 wisdom) and vest (adventurer_vest) are no longer
            # the argmax — the combat helmet hard_leather_helmet (combat_raw 93
            # vs wolf_ears' 66) and mushmush_jacket outrank them, so they were
            # structural candidates masking the utility comparison. Equipping
            # the true pursuit_value argmax in both restores this scenario's
            # "no structural gear candidate" design intent (band-adequate), so
            # the XP-outranks-empty-utility verdict is isolated again.
            # RE-FIXED-POINT 2026-08-04 (pursuit_value unification):
            # `near_term_gear` ranks on `pursuit_value`, whose combat term is
            # now the ONE gear ruler's own, so slots that were a fixed point
            # only for the retired flat `combat_raw` sum are re-converged here.
            # Without this the scenario leaks unrelated candidates into the
            # ranking and stops isolating the gap it was built for.
            "weapon_slot": "battlestaff", "helmet_slot": "hard_leather_helmet",
            "body_armor_slot": "mushmush_jacket", "leg_armor_slot": "hard_leather_pants",
            "boots_slot": "hard_leather_boots", "ring1_slot": "steel_ring",
            # ring2 RE-DERIVED (Task 2, GAP-2 review, 2026-07-08): rings are
            # duplicate-allowed, so the true near_term_gear fixed point is a
            # 2nd life_ring (the argmax attainable-now ring, matching ring1)
            # rather than the weaker forest_ring a distinct-ranked-fill used
            # to leave in place — restores this scenario's "no structural
            # gear candidate" design intent.
            "ring2_slot": "steel_ring", "amulet_slot": "air_and_water_amulet",
            "shield_slot": "iron_shield", "bag_slot": "satchel",
            "artifact1_slot": "perfect_pearl", "artifact2_slot": "perfect_pearl",
            "artifact3_slot": "perfect_pearl",
        },
        bank={"nettle_leaf": 30, "algae": 15},
        derive_combat_stats=True,
        description="L20 band-adequate, BOTH utility slots empty, potion "
                     "mats banked — pins that the XP branch outranks the "
                     "utility fill (utility1 root demoted to fallback)."),
    # The second-slot probe: utility1 already stocked with the bootstrap
    # target. Same RE-DERIVED fixed-point loadout as l20_dual_utility above.
    # GAP-5 FIXED 2026-07-07: utility_potion_targets now emits BOTH slots
    # (utility2 gets the catalog's second-best heal). The per-slot stock
    # check that used to let utility2_slot survive into `_utility_candidates`
    # while slot 1 was skipped lived ONLY in that function, which wave 3b
    # deleted (zero production callers since wave 3a stopped reading it) —
    # so as of wave 3b no potion reaches `fallback_roots` at all, stocked or
    # not (utility slots aren't equipment slots `gear_targets_with_blockers`
    # sees). This scenario now exercises that absence rather than a win.
    "l20_dual_utility_one_stocked": ScenarioCharacter(
        name="l20_dual_utility_one_stocked", level=20, gold=100,
        skills={"mining": 18, "woodcutting": 18, "weaponcrafting": 15,
                "gearcrafting": 15, "fishing": 15, "cooking": 15,
                "alchemy": 20, "jewelrycrafting": 10},
        equipment={
            # helmet/body RE-FIXED-POINT 2026-07-08 (Task-3 pursuit_value) —
            # see l20_dual_utility's comment; same combat-argmax fixed point.
            # RE-FIXED-POINT 2026-08-04 (pursuit_value unification):
            # `near_term_gear` ranks on `pursuit_value`, whose combat term is
            # now the ONE gear ruler's own, so slots that were a fixed point
            # only for the retired flat `combat_raw` sum are re-converged here.
            # Without this the scenario leaks unrelated candidates into the
            # ranking and stops isolating the gap it was built for.
            "weapon_slot": "battlestaff", "helmet_slot": "hard_leather_helmet",
            "body_armor_slot": "mushmush_jacket", "leg_armor_slot": "hard_leather_pants",
            "boots_slot": "hard_leather_boots", "ring1_slot": "steel_ring",
            # ring2 RE-DERIVED (Task 2, GAP-2 review, 2026-07-08) — see
            # l20_dual_utility's comment; same fixed-point loadout.
            "ring2_slot": "steel_ring", "amulet_slot": "air_and_water_amulet",
            "shield_slot": "iron_shield", "bag_slot": "satchel",
            "artifact1_slot": "perfect_pearl", "artifact2_slot": "perfect_pearl",
            "artifact3_slot": "perfect_pearl",
            "utility1_slot": "minor_health_potion",
        },
        utility_quantities={"utility1_slot": 15},
        bank={"nettle_leaf": 30, "algae": 15},
        derive_combat_stats=True,
        description="l20_dual_utility with utility1 stocked — pins that "
                     "utility2_slot is unreachable by the tree (no "
                     "candidate, no fallback)."),

    # --- GAP-8: craft chain with a monster-drop ingredient (2026-07-08,
    # LIVE STALL witness). Mirror of live Robby the day the stall was traced
    # (character + bank queried via the API, at full HP): L13, weaponcrafting
    # 5, the tree's root is the fire_bow weapon upgrade (its own mats —
    # spruce_plank 6 + red_slimeball 2 — are already in the bag, so the
    # material step is satisfied) and the step is fire_bow's weaponcrafting
    # skill gate (5 < 10). The retired tree-level skill-grind dispatch picked
    # water_bow (the level-5 grinder with the fewest missing mats once the
    # banked blue_slimeballs are credited: 2x blue_slimeball [monster drop,
    # bank 2 + bag 1] + 5x ash_plank [10 ash_wood each]). Before the GAP-8
    # fix, craft_plan_gen bailed on ANY closure with a monster-drop leaf —
    # even this bank-covered one — and the raw A* fallback flooded >50K
    # nodes into timeout/plan_len 0 (live: 38,124 nodes, 65 consecutive
    # cycles of GrindCharacterXP(red_slime); weaponcrafting frozen).
    # Pinned by tests/test_ai/scenarios/test_craft_drop_chains.py.
    "l13_drop_recipe_grind": ScenarioCharacter(
        name="l13_drop_recipe_grind", level=13, gold=2299,
        skills={"mining": 12, "woodcutting": 10, "weaponcrafting": 5,
                "gearcrafting": 10, "alchemy": 16, "cooking": 5,
                "fishing": 3, "jewelrycrafting": 5},
        equipment={
            "weapon_slot": "copper_pickaxe", "helmet_slot": "iron_helm",
            "body_armor_slot": "feather_coat", "leg_armor_slot": "copper_legs_armor",
            "boots_slot": "iron_boots", "ring1_slot": "copper_ring",
            "ring2_slot": "copper_ring", "amulet_slot": "life_amulet",
            "shield_slot": "wooden_shield", "artifact1_slot": "novice_guide",
        },
        inventory={
            "copper_ring": 2, "copper_axe": 9, "red_slimeball": 17,
            "fishing_net": 7, "recall_potion": 10, "copper_boots": 1,
            "copper_helmet": 1, "algae": 5, "wooden_staff": 1, "ash_wood": 1,
            "spruce_plank": 6, "sap": 1, "blue_slimeball": 1,
            "emerald_stone": 1, "wool": 1, "topaz_stone": 1,
            "sapphire_stone": 3,
        },
        inventory_max=124,
        bank={
            "apple": 13, "blue_slimeball": 2, "copper_dagger": 1,
            "copper_helmet": 1, "copper_legs_armor": 1, "copper_ring": 2,
            "egg": 1, "emerald_stone": 15, "red_slimeball": 37,
            "ruby_stone": 27, "sap": 41, "sapphire_stone": 28,
            "topaz_stone": 28, "wooden_shield": 1,
        },
        derive_combat_stats=True,
        # HELD TASK, value "unwinnable but a gear chain CLOSES it" (measured:
        # has_combat_deficit True, deficit_upgrade_target ('iron_sword',
        # 'weapon_slot')). This is the "I lost, so get gear" link the bot spent
        # ten hours without; the arm had no offline witness. Measured not to
        # move this scenario's chosen root/step/goal/first action.
        task=("cow", "monsters", 4, 10),
        description="Live-Robby mirror (2026-07-08): L13, weaponcrafting 5, "
                     "fire_bow root -> weaponcrafting skill gate -> "
                     "water_bow grinder whose recipe has a monster-drop leaf "
                     "(blue_slimeball) — the craft chain must plan instead "
                     "of flooding A* and falling back to the red_slime "
                     "grind."),

    # --- Gear-pursuit correctness Task 1 (2026-07-09, docs/superpowers/sdd
    # gear-pursuit-correctness plan): no-deadlock criterion 1 witness. L10,
    # full copper set (L1/L5 tier), mining 10 (meets iron_ore's gather-level
    # gate — iron_rocks requires mining 10) but weaponcrafting/gearcrafting
    # only 5 (below iron_boots' craft-skill gate of 10). iron_boots
    # (gearcrafting 10, item level 10 <= state.level, recipe iron_bar x5 +
    # feather x3, both closures open at this state: iron_ore gathers at
    # mining 10, feather drops off the chicken) is a real near_term_gear
    # candidate — the planner must target it via the craft/skill-grind
    # path, NOT fall back to a character-level grind, when the blocking gap
    # is a CRAFTING skill rather than combat viability.
    #
    # RE-DERIVED from the investigation's original "L12" framing (2026-07-09
    # Task 1): at L12 the chicken (level 1) reads as a GREY dropper
    # (xp_per_kill formula zeroes at level-diff >= 11; 12-1=11), which routes
    # feather acquisition through `grey_farm_allowed` — and that policy's
    # "nearest consumer" arm picks `apprentice_gloves` (weaponcrafting level
    # 1, the LOWEST-level recipe that consumes feather, not iron_boots) as
    # the reference recipe, whose next tier is within the grind-margin at
    # weaponcrafting 5 — so grey-farming feather is SUPPRESSED and
    # GatherMaterials(feather) has no action to reach its target at all
    # (plan_len 0), and the arbiter falls through to GrindCharacterXP after
    # all. That is a real planner finding, but it is an ARTIFACT of the
    # chicken/apprentice_gloves grey-farm interaction, not the craft-skill
    # criterion this scenario exists to witness. At L10 (diff 10-1=9, still
    # inside the xp-positive window) chicken is a normal winnable dropper —
    # FightAction(chicken) is emitted unconditionally (no grey-farm gate
    # consulted) — and the craft/skill-grind chain runs cleanly. Confirmed
    # by direct planner run (see docs/superpowers/sdd/task-1-report.md).
    "l10_gearcrafting_gap": ScenarioCharacter(
        name="l10_gearcrafting_gap", level=10,
        skills={"mining": 10, "weaponcrafting": 5, "gearcrafting": 5},
        # RE-FIXED-POINT 2026-08-04 (pursuit_value unification): was
        # `dict(_COPPER_SET)`. Once `near_term_gear` ranks on the ONE gear
        # ruler's own combat term, seven other slots open L10-tier candidates
        # that outrank the boots and this scenario stops isolating its
        # crafting-skill gap. Every slot EXCEPT boots is converged to the
        # ruler's fixed point; boots_slot is deliberately left a tier behind
        # so iron_boots remains the sole candidate, which is the criterion.
        equipment={**_COPPER_SET,
                   "weapon_slot": "greater_wooden_staff",
                   "helmet_slot": "iron_helm",
                   "body_armor_slot": "adventurer_vest",
                   "leg_armor_slot": "iron_legs_armor",
                   "ring1_slot": "iron_ring", "ring2_slot": "iron_ring",
                   "shield_slot": "iron_shield",
                   "amulet_slot": "air_and_water_amulet"},
        derive_combat_stats=True,
        description="Criterion 1 (no-deadlock-on-skilling-gear): L10, copper "
                     "gear, mining 10 / gearcrafting+weaponcrafting 5 — "
                     "iron_boots is a reachable near_term_gear candidate "
                     "gated on a CRAFTING skill, not combat; the planner "
                     "must pursue ObtainItem(iron_boots) via a gather/craft "
                     "skill-grind step (GatherMaterials(feather) -> "
                     "Fight(chicken)), never GrindCharacterXP."),

    # GAP-9 regression (2026-07-08): at L12 the feather-dropping chicken (L1)
    # is GREY (level diff 11 >= 10 -> zero xp), so the feather leaf must go
    # through grey_farm_allowed. The old lowest-consumer heuristic evaluated
    # feather against apprentice_gloves (an unrelated gc1 tool with a near
    # next tier) and wrongly suppressed the farm -> GatherMaterials(feather)
    # unplannable -> the whole plan deadlocked to GrindCharacterXP even though
    # a committed iron_boots (gc10, far next boot tier) genuinely needed the
    # feather. The ANY-consumer policy allows the farm. iron_bar is pre-banked
    # so the remaining unmet material IS the grey-farmed feather.
    "l12_gearcrafting_gap": ScenarioCharacter(
        name="l12_gearcrafting_gap", level=12,
        skills={"mining": 10, "woodcutting": 10, "weaponcrafting": 5,
                "gearcrafting": 5, "jewelrycrafting": 5, "cooking": 5,
                "alchemy": 5, "fishing": 5},
        # RE-FIXED-POINT 2026-08-04 — see l10_gearcrafting_gap. Same converged
        # loadout, boots_slot held a tier behind so the grey-farmed feather
        # leaf this scenario exists to pin is still the binding constraint.
        equipment={**_COPPER_SET,
                   "weapon_slot": "greater_wooden_staff",
                   "helmet_slot": "iron_helm",
                   "body_armor_slot": "adventurer_vest",
                   "leg_armor_slot": "iron_legs_armor",
                   "ring1_slot": "iron_ring", "ring2_slot": "iron_ring",
                   "shield_slot": "iron_shield",
                   "amulet_slot": "air_and_water_amulet"},
        bank={"iron_bar": 10},
        derive_combat_stats=True,
        # HELD TASK, value "workable" (measured: has_combat_deficit False,
        # deficit_upgrade_target None) -- the NEGATIVE arm of the deficit check,
        # which needs a task that IS winnable to be reached at all. Measured not
        # to move this scenario's chosen root/step/goal/first action.
        task=("cow", "monsters", 4, 10),
        description="GAP-9: L12, copper gear, gearcrafting 5, iron_bar banked "
                     "-> the committed iron_boots upgrade needs feather from a "
                     "GREY chicken (diff 11). The planner must farm feather "
                     "(GatherMaterials(feather) -> Fight(chicken) drop-farm), "
                     "never deadlock to GrindCharacterXP. Fixed by the "
                     "any-consumer grey-farm policy (was suppressed against "
                     "the unrelated lowest feather consumer)."),

    # --- Criterion-1 ramp: the same character, but the iron_boots material
    # closure's feather leaf is now combat-blocked (no winnable dropper) —
    # chicken is removed from this scenario's reachable monster set by
    # leaving combat stats at the harness's zero-stat default
    # (derive_combat_stats=False; l1_fresh/l8_overstocked use the same
    # convention for "no monster is winnable here" — is_winnable sees 0
    # attack against every monster). Pins the ramp: the planner must
    # re-target a reachable candidate or Wait, never thrash GrindCharacterXP
    # against an unwinnable monster.
    "l10_gearcrafting_gap_combat_blocked": ScenarioCharacter(
        name="l10_gearcrafting_gap_combat_blocked", level=10, max_hp=240,
        skills={"mining": 10, "weaponcrafting": 5, "gearcrafting": 5},
        equipment=dict(_COPPER_SET),
        description="Criterion-1 ramp: l10_gearcrafting_gap with combat "
                     "stats at the harness's zero-attack default (no "
                     "derive_combat_stats) so every monster including the "
                     "feather-dropping chicken reads unwinnable — the "
                     "iron_boots closure is combat-blocked. Pins that the "
                     "planner re-targets to a reachable candidate (the "
                     "utility-potion branch) instead of thrashing "
                     "GrindCharacterXP against an unwinnable monster."),
    # Live Robby 2026-08-03 (L21, jewelrycrafting 14), 8 of 16 consecutive
    # cycles of `LevelSkill(jewelrycrafting->15) -> error:other`. The banked
    # iron_bar makes iron_ring (jewelrycrafting 10) the cheapest in-skill rung,
    # so the grind descends to its OTHER material, wool — a mob-only drop whose
    # sole source is the level-5 sheep, GREY at 21. Reproduces the exact live
    # goal `GatherMaterials(wool, {wool:2})`.
    "l21_grey_material_grind": ScenarioCharacter(
        name="l21_grey_material_grind", level=21, gold=500,
        derive_combat_stats=True,
        skills={"alchemy": 16, "cooking": 12, "fishing": 5, "gearcrafting": 15,
                "jewelrycrafting": 14, "mining": 21, "weaponcrafting": 10,
                "woodcutting": 15},
        equipment={
            "weapon_slot": "highwayman_dagger", "helmet_slot": "lucky_wizard_hat",
            "body_armor_slot": "mushmush_jacket", "leg_armor_slot": "adventurer_pants",
            "boots_slot": "adventurer_boots", "ring1_slot": "air_ring",
            "amulet_slot": "wisdom_amulet",
        },
        bank={"iron_bar": 6},
        inventory_max=140,
        description="L21 jewelrycrafting-14 grind whose rung (iron_ring) needs "
                     "wool, a drop of the GREY level-5 sheep: the skill-grind "
                     "grey-farm exemption is what makes it plannable."),
    "l22_grey_rung_grind": ScenarioCharacter(
        name="l22_grey_rung_grind", level=22, gold=8431,
        derive_combat_stats=True,
        skills={"alchemy": 17, "cooking": 12, "fishing": 5, "gearcrafting": 15,
                "jewelrycrafting": 15, "mining": 21, "weaponcrafting": 10,
                "woodcutting": 15},
        equipment={
            "weapon_slot": "highwayman_dagger", "helmet_slot": "lucky_wizard_hat",
            "body_armor_slot": "mushmush_jacket", "leg_armor_slot": "adventurer_pants",
            "boots_slot": "adventurer_boots", "ring1_slot": "air_ring",
            "amulet_slot": "wisdom_amulet",
        },
        # THE TRAP, verbatim from the live state: a pile of ash_wood makes the
        # grey `ash_plank` (woodcutting 1) the rung with ZERO missing materials,
        # so it wins `mats_missing` — the selector's first non-`wanted` key —
        # against `spruce_plank` (woodcutting 10), which needs spruce_wood.
        # `ash_plank`'s craft pays nothing 14 levels down, so the pre-fix grind
        # crafted it forever. The ash pile is ALSO what the objective is
        # accumulating (hardwood_plank = 4 ash_wood + 6 birch_wood), which is
        # what makes this scenario carry BOTH defects at once.
        inventory={"ash_wood": 40},
        inventory_max=142,
        # NO spruce_wood anywhere. This is load-bearing, not incidental: with
        # spruce banked, `spruce_plank` ALSO scores mats_missing 0, the tie falls
        # through to `craft_level` (higher wins) and the paying rung is selected
        # even with the xp filter removed — i.e. the scenario would be VACUOUS.
        # Robby was mid-`SupplyBank(spruce_wood x60)` precisely because he had
        # none, which is what let the grey rung win outright.
        bank={},
        description="L22 woodcutting-15 chasing hardwood_plank (4 ash_wood + 6 "
                     "birch_wood, birch_tree needs woodcutting 20). The grind "
                     "rung must PAY XP (ash_plank at gap 14 does not) and must "
                     "not EAT the objective's ash_wood. Live Robby 2026-08-05: "
                     "14h, 660 cycles, character level 22 -> 22."),
    "l12_deep_chain_grind": ScenarioCharacter(
        name="l12_deep_chain_grind", level=12, gold=268,
        derive_combat_stats=True,
        # Live R2D2 2026-08-06. weaponcrafting 5 is the grind under test; mining
        # 12 is what makes its chosen chain worthless, because copper_rocks is a
        # level-1 resource and 12 - 1 = 11 >= GREY_SKILL_GAP.
        skills={"alchemy": 4, "cooking": 4, "fishing": 1, "gearcrafting": 8,
                "jewelrycrafting": 2, "mining": 12, "weaponcrafting": 5,
                "woodcutting": 11},
        equipment={
            "weapon_slot": "wooden_staff", "helmet_slot": "copper_helmet",
            "body_armor_slot": "copper_armor", "leg_armor_slot": "copper_legs_armor",
            "boots_slot": "copper_boots", "ring1_slot": "copper_ring",
        },
        # THE TRAP: `yellow_slimeball` in the bank covers 2 of sticky_sword's
        # recipe, leaving `copper_bar: 5` — so the OLD one-level count scored
        # sticky_sword 5 and `apprentice_gloves` (6 feather) 6, and the sword won
        # by one. Each of those 5 bars is 10 copper_ore, so the sword is really
        # ~51 actions against the gloves' 7, and every one of those ore gathers
        # is grey at mining 12. No copper_bar and no feather held, so both chains
        # must be costed from their leaves — which is the whole point.
        inventory={"copper_ore": 1},
        bank={"yellow_slimeball": 8},
        inventory_max=122,
        description="L12 weaponcrafting-5 whose cheapest-LOOKING rung "
                     "(sticky_sword, 5 recipe entries) is really ~51 actions of "
                     "zero-xp copper_ore gathering, against apprentice_gloves at "
                     "7. Live R2D2: 129 grind cycles, weaponcrafting never moved."),
    # --- Band-EDGE fixtures (bounded-horizon spike, Tool 3, 2026-08-18).
    # Every other scenario sits mid-band or at a band ENTRY, so the suite has
    # never covered the two positions where a level-denominated horizon
    # degenerates. Measured live: a character one level from its milestone
    # projects the SAME cycles-to-milestone for every candidate (R2D2 L19,
    # spread 0 over 9 candidates), while one four levels out spreads 1,086 over
    # 12. The horizon is measured in LEVELS and the quantity compared is
    # measured in CYCLES, and the distance between them swings by an order of
    # magnitude purely with band position — which is invisible without these two.
    #
    # `derive_combat_stats=True` is LOAD-BEARING here, not decoration. Without
    # it the character carries zero attack, `is_winnable` is False against every
    # monster (see the flag's own docstring), and `cheapest_path_to_level` blocks
    # at rung one — so the scenario would report a flat benefit column for a
    # reason that has nothing to do with the band position it exists to isolate.
    # Both are modelled on `l21_grey_material_grind`'s gear and skill shape so
    # the pair differs from it, and from each other, in LEVEL and nothing else.
    "l19_band_edge": ScenarioCharacter(
        name="l19_band_edge", level=19, gold=500,
        derive_combat_stats=True,
        skills={"alchemy": 16, "cooking": 12, "fishing": 5, "gearcrafting": 15,
                "jewelrycrafting": 14, "mining": 21, "weaponcrafting": 10,
                "woodcutting": 15},
        equipment={
            "weapon_slot": "highwayman_dagger", "helmet_slot": "lucky_wizard_hat",
            "body_armor_slot": "mushmush_jacket", "leg_armor_slot": "adventurer_pants",
            "boots_slot": "adventurer_boots", "ring1_slot": "air_ring",
            "amulet_slot": "wisdom_amulet",
        },
        bank={"iron_bar": 6},
        inventory_max=140,
        description="ONE level below the L20 milestone: the horizon's flat end, "
                     "where every candidate projects the same cycles to the "
                     "milestone and the objective cannot discriminate."),
    "l11_band_floor": ScenarioCharacter(
        name="l11_band_floor", level=11, gold=500,
        derive_combat_stats=True,
        skills={"alchemy": 16, "cooking": 12, "fishing": 5, "gearcrafting": 15,
                "jewelrycrafting": 14, "mining": 21, "weaponcrafting": 10,
                "woodcutting": 15},
        equipment={
            "weapon_slot": "highwayman_dagger", "helmet_slot": "lucky_wizard_hat",
            "body_armor_slot": "mushmush_jacket", "leg_armor_slot": "adventurer_pants",
            "boots_slot": "adventurer_boots", "ring1_slot": "air_ring",
            "amulet_slot": "wisdom_amulet",
        },
        bank={"iron_bar": 6},
        inventory_max=140,
        description="NINE levels below the L20 milestone: the horizon's long "
                     "end, where a banded projection walks the most rungs and "
                     "an acquisition has the most room to repay itself."),

    # --- COVERAGE MATRIX cells 1-3 (design 2026-08-24 §5.3): the HELD-TASK
    # dimension as a CONTROLLED triple. Three scenarios already hold a task
    # (`l12_gearcrafting_gap`, `l13_drop_recipe_grind`, `l10_copper_adequate`)
    # and between them cover the same three values — but on three DIFFERENT
    # characters, so nothing they measure can be attributed to the task rather
    # than to the level, gear or bank that also differ. These three are ONE
    # character in three task states: every field below is identical across
    # them and `task` is the only thing that moves, which is what makes the
    # dimension the thing under test.
    #
    # D1 = derived, mandatory here. Measured (design §5.1 I1): at zero total
    # attack a `cow` task gives `has_combat_deficit` in 30/30 scenarios and a
    # `chicken` task in 29/30, because every monster is unwinnable — so a task
    # cell on the zero-attack side measures the harness, not the bot. The
    # D1=zero half of this pair is deliberately NOT built.
    #
    # Packed independent dimensions (§5.3's "packs" column, taken as a set over
    # the triple rather than split across it — splitting them would confound the
    # only comparison these three exist to make): D8 mid-band (32 sits between
    # the 30 and 35 ladder rungs), D9 >= 10k (live 82.3 % of cycles hold >= 1000
    # gold; the committed set had 3/30), D6 non-empty bag but well below every
    # relief watermark (live: 0 of 80,194 cycles carry an empty bag; the
    # committed set carried one in 26/30) and D7 stocked.
    #
    # The three monsters are catalogue facts at this loadout, not guesses —
    # RE-MEASURED 2026-08-26 over all 58 monsters: 12 workable, 8
    # unwinnable-with-a-closing-chain, 38 unwinnable-with-none.
    #
    # THE SPLIT INVERTED, and the old numbers (37 closing / 9 none) are kept
    # here only to name what changed: `e6a2e37c` taught `deficit_upgrade_target`
    # to honour `closes`, so the 29 monsters it used to name gear for — gear
    # that provably could not win — now correctly report no chain. The three
    # cells below are unaffected: their verdicts were re-measured and each still
    # sits in the arm its comment claims.
    #
    # The `level_up` band is EMPTY at this loadout: 0 of 58 monsters, which is
    # why the triple has no fourth member. That verdict IS witnessed, on a
    # different character: `test_held_task.py`'s STARVED triple injects a task
    # onto `l48_capstone_approach` and drives all three verdicts through
    # `plan_from_state`.
    # D2 = WORKABLE. `pig` is the monster C3P0 lost 42 straight fights to at
    # level 19; at this loadout it is winnable, so `has_combat_deficit` is
    # False and `deficit_upgrade_target` is None through its FIRST return.
    # THE ITEMS-TASK CELL, and the only one in the set. Built from the SAME
    # `_held_task_cell` loadout as the monsters triple below, so the one thing
    # that differs from `l32_held_task_workable` is the task's TYPE — which is
    # what makes it a control for every consumer that branches on
    # `task_type == "items"`.
    #
    # FOUR PRODUCTION CONSUMERS were unreachable offline before it, all of them
    # live code: `craft_relief.py:196` (cap crafting by remaining task units),
    # `inventory_caps.py:434`, `inventory_keep.py:301` (keep the task item), and
    # `objective_step_fight_core.py:61` (a >4-level grind stands down for an
    # in-progress items task). They had unit coverage over hand-built states and
    # no end-to-end path at all.
    #
    # LIVE THIS IS UNOBSERVED: 0 items tasks in 15,240 task-cycles, every one a
    # `monsters` task. The economy is modelled and never exercised, which is
    # exactly why the fixture is worth more than another monsters cell.
    #
    # `apprentice_gloves` IS MEASURED, NOT CHOSEN FOR PLAUSIBILITY. Swept over
    # every craftable item in the bundle at this loadout, it is the ONLY task
    # code that makes `craft_relief_candidates` fire (control, no task: empty).
    # `copper_bar` was the first pick and produced [] on BOTH arms — the cell
    # holds `iron_ore`, not copper. Even `iron_bar` fails, for a subtler reason
    # worth recording: 12 iron_ore covers its 10-ore recipe, but the bar is not
    # already in the bag, so crafting it ADDS a stack and fails the SLOT gate
    # that `craft_relief` exists to respect.
    #
    # Keep demand moves 0 -> 8 (the remaining units) on the same cell, so the
    # keep and craft consumers both have work rather than reading a task they
    # cannot act on.
    "l32_items_task": _held_task_cell(
        "l32_items_task", ("apprentice_gloves", "items", 2, 10),
        "Held ITEMS task, 2/10 apprentice_gloves — the only items-type task in "
        "the set, and the sole offline witness for the consumers that branch "
        "on it."),
    "l32_held_task_workable": _held_task_cell(
        "l32_held_task_workable", ("pig", "monsters", 4, 10),
        "Held-task triple, value WORKABLE: a pig task this loadout wins — "
        "the negative arm of the deficit check."),
    # D2 = UNWINNABLE, A GEAR CHAIN CLOSES IT. The greedy margin walk names
    # `perfect_bow` unpriced and `earth_boost_potion` under the GEAR_REVIEW
    # guard's `acquisition_actions` pricing — either way it names SOMETHING,
    # which is the "I lost, so get gear" link, and the input that makes
    # `strategy_driver`'s GEAR_REVIEW arm pick a MONSTER-AWARE target instead
    # of falling through to the monster-blind value scan.
    "l32_held_task_closable": _held_task_cell(
        "l32_held_task_closable", ("ogre", "monsters", 4, 10),
        "Held-task triple, value UNWINNABLE-CLOSABLE: an ogre task this "
        "loadout loses and `perfect_bow` closes."),
    # D2 = UNWINNABLE, NOTHING CLOSES IT. `lich` is level 30 against this
    # character's 32 — IN BAND, so the fall-through is not an artefact of
    # picking an absurd monster — and no single acquisition in the catalogue
    # improves the margin, so the walk runs to exhaustion and names nothing.
    "l32_held_task_open": _held_task_cell(
        "l32_held_task_open", ("lich", "monsters", 4, 10),
        "Held-task triple, value UNWINNABLE-OPEN: an in-band lich task no "
        "gear in the catalogue closes."),

    # --- COVERAGE MATRIX cells 4, 5 and 7 (design §5.3): the GRAND-EXCHANGE
    # dimension, as a controlled triple over ONE character. Cell 7 is the
    # CONTROL and exists because cells 4 and 5 prove nothing without it.
    #
    # All three stand on the same rung shape: `feather_coat`
    # (gearcrafting 10, recipe {feather:5, ash_plank:2}) is depth-2 and
    # DROP-FED — `feather` comes off the chicken, `ash_plank` from `ash_wood`.
    # That shape is 70.7 % of the catalogue and 87.2 % of live UpgradeEquipment
    # cycles, and it carried 4/30 scenarios. `feather_coat` also carries a
    # standing GE sell order in the captured book, which is what puts the
    # `_source_leafs` GE arm on the descent at all.
    # D11 = ONE SHORT (gearcrafting 9 against the rung's 10), so the descent is
    # a GRIND descent and `_source_leafs` takes its `CRAFT_SUBSTITUTE_KINDS`
    # arm: the standing GE order must NOT end the walk, because buying the rung
    # pays zero skill XP. This is the Robby stall of 2026-08-24 as a scenario.
    "l12_ge_book_grind": _ge_market_cell(
        "l12_ge_book_grind", gearcrafting=9, ge_market=True,
        description="GE triple, cell 4: busy order book, gearcrafting ONE "
                    "SHORT of the rung — the grind must descend PAST the "
                    "standing GE sell order to the material it has to gather."),
    # THE CONTROL. Character-identical to `l12_ge_book_grind`; the ONLY
    # difference in the whole world is that no order stands on anything, so
    # `obtain_sources` emits no GE_FILL and the GE arm of `_source_leafs` is
    # never reached. Without this row, cell 4's descent could be right for a
    # reason that has nothing to do with the order book.
    "l12_quiet_book_grind": _ge_market_cell(
        "l12_quiet_book_grind", gearcrafting=9, ge_market=False,
        description="GE triple, cell 7 (CONTROL): the same character as "
                    "l12_ge_book_grind in a QUIET market — no standing order, "
                    "so the GE leaf rule is never consulted."),
    # D11 = ADEQUATE, so the descent is NOT a grind and `_source_leafs` takes
    # its other arm: a GE_FILL DOES leaf, because here the item is the goal
    # rather than the craft. Measured: this character plans
    # `GeBuy(iron_legs_armor)` in the busy book and `Gather(iron_rocks x42)` in
    # the quiet one — the sharpest single flip the GE dimension produces.
    "l12_ge_book_adequate": _ge_market_cell(
        "l12_ge_book_adequate", gearcrafting=10, ge_market=True,
        description="GE triple, cell 5: busy order book, gearcrafting ADEQUATE "
                    "— outside a grind the standing GE order LEAFS the descent "
                    "and the rung is bought rather than crafted."),

    # --- COVERAGE MATRIX cell 6 (design §5.3): D4 = a DEPTH-3 rung.
    # Nine catalogue recipes close at depth 3 and NO scenario put one on a
    # gear sheet, so the deepest closure the harness ever walked was depth 2.
    # `greater_dreadful_amulet` ({gold_bar:8, dreadful_amulet:1, cyclops_eye:4,
    # ogre_eye:4, red_cloth:3}) is one of the nine: `dreadful_amulet` is itself
    # a recipe ({hardwood_plank:6, ogre_eye:4, hard_leather:2, king_slimeball:2})
    # and `hardwood_plank` is a third ({ash_wood:4, birch_wood:6}).
    #
    # Reaching it needs a CHARACTER, not a field (design §4.3). `gear_target_tier`
    # is the rung being CLEARED, so a level-47 character in the best catalogue
    # loadout at or below its own level clears through rung 25 and gears for
    # rung 30 — at which the amulet slot's best candidate IS the depth-3 amulet.
    # The slot is left EMPTY so it is the one slot behind its target; every other
    # worn piece already outvalues its rung-30 candidate.
    # The bag holds every root input EXCEPT `dreadful_amulet`, which is what
    # forces the descent through the depth-3 leg instead of stopping at a drop.
    # D1 derived and D8 mid-band (47 sits between rungs 45 and 50) per §5.3.
    "l47_depth3_amulet": ScenarioCharacter(
        name="l47_depth3_amulet", level=47,
        skills={"mining": 40, "woodcutting": 40, "weaponcrafting": 40,
                "gearcrafting": 40, "jewelrycrafting": 40, "cooking": 20,
                "alchemy": 20, "fishing": 20},
        equipment={
            "helmet_slot": "darkforged_helmet", "weapon_slot": "hell_reaper",
            "shield_slot": "darkforged_shield", "ring1_slot": "hell_ring",
            "ring2_slot": "hell_ring", "boots_slot": "darkforged_boots",
            "leg_armor_slot": "mesh_legs_armor",
            "body_armor_slot": "darkforged_plate",
            "utility1_slot": "greater_health_potion",
            "utility2_slot": "small_health_potion",
        },
        inventory={"gold_bar": 8, "cyclops_eye": 4, "ogre_eye": 8,
                   "red_cloth": 3, "hard_leather": 2, "king_slimeball": 2,
                   "greater_health_potion": 6},
        utility_quantities={"utility1_slot": 40, "utility2_slot": 40},
        inventory_max=150, bank={}, gold=9000, derive_combat_stats=True,
        description="Cell 6: a DEPTH-3 gear rung (greater_dreadful_amulet) — "
                    "the descent must walk root -> dreadful_amulet -> "
                    "hardwood_plank -> ash_wood, two levels deeper than any "
                    "other scenario reaches."),

    # --- COVERAGE MATRIX cell 8 (design §5.3): D6 >= 75 % x D7 STOCKED.
    # The three relief guards fired in 0/36 scenarios. All three need bag
    # pressure; RECYCLE_RELIEF and SELL_RELIEF additionally need the bank to
    # have NO ROOM (`bank_has_room` is `len(bank_items) < game_data.bank_capacity`,
    # and the bundle's capacity is 50), which is what "stocked" has to mean for
    # this cell — a bank with room routes the pressure to DEPOSIT_FULL instead.
    #
    # The pressure is on the SLOT axis (16 of 20 slots = 0.80) and NOT the
    # quantity axis (118 of 200 = 0.59), which is the live Robby 2026-07-10
    # shape and the reason `_used_fraction` takes the max of the two. Keeping
    # quantity low is deliberate: both DISCARD guards read the QUANTITY
    # fraction, so at 0.59 neither can preempt the guards this cell exists to
    # exercise (design §5.2's masking rule).
    # `timber_merchant` is declared active because EVERY item-buying NPC in the
    # game is an event NPC — without an open window `sellable_tradeable_now` is
    # False by construction and SELL_RELIEF could never fire.
    # Packs D2 none and D9 mid (1,500 gold) per §5.3.
    "l20_relief_full_bank": ScenarioCharacter(
        name="l20_relief_full_bank", level=20,
        skills={"mining": 20, "woodcutting": 20, "weaponcrafting": 15,
                "gearcrafting": 15, "jewelrycrafting": 15, "cooking": 10,
                "alchemy": 10, "fishing": 10},
        equipment=dict(_IRON_SET),
        inventory={"ash_wood": 20, "iron_ore": 12, "copper_ore": 10,
                   "cowhide": 8, "feather": 6, "spruce_wood": 10,
                   "iron_helm": 2, "sap": 9, "birch_wood": 8,
                   "yellow_slimeball": 7, "gudgeon": 6, "raw_chicken": 5,
                   "sunflower": 5, "milk_bucket": 4, "copper_bar": 3,
                   "mushroom": 3},
        inventory_max=200, inventory_slots_max=20,
        bank=dict(_FULL_BANK), gold=1500,
        active_events=("timber_merchant",), derive_combat_stats=True,
        description="Cell 8: bag at 80 % of its SLOT cap against a bank with "
                    "no room — CRAFT_RELIEF, RECYCLE_RELIEF and SELL_RELIEF "
                    "all fire, and none of them could before."),

    # --- COVERAGE MATRIX cell 9 (design §5.3): D6 >= 90 % (PREEMPTING) x D7 EMPTY.
    # The mirror image of cell 8, and deliberately so: the pressure is on the
    # QUANTITY axis (152 of 160 = 0.95, clearing DISCARD_CRITICAL's 0.95 rung)
    # while only 5 of 20 slots are used, and the bank is EMPTY so it has room.
    # That combination is what puts DEPOSIT_FULL and DISCARD_CRITICAL up
    # together — the pair §5.3 names — while cell 8's guards stay silent
    # (CRAFT_RELIEF reads the same `_used_fraction` max and 0.95 clears it, so
    # its absence here is `craft_relief_candidates` being empty, not the
    # watermark).
    "l20_bag_critical_empty_bank": ScenarioCharacter(
        name="l20_bag_critical_empty_bank", level=20,
        skills={"mining": 20, "woodcutting": 20, "weaponcrafting": 15,
                "gearcrafting": 15, "jewelrycrafting": 15, "cooking": 10,
                "alchemy": 10, "fishing": 10},
        equipment=dict(_IRON_SET),
        inventory={"feather": 60, "sap": 42, "yellow_slimeball": 30,
                   "raw_chicken": 12, "ash_wood": 8},
        inventory_max=160, inventory_slots_max=20, bank={}, gold=1500,
        derive_combat_stats=True,
        description="Cell 9: bag at 95 % of its QUANTITY cap against an EMPTY "
                    "bank — DISCARD_CRITICAL and DEPOSIT_FULL both fire."),

    # --- COVERAGE MATRIX cell 10 (design §5.3): D10 = HP 50-99 %, PREEMPTING.
    # `REST_FOR_COMBAT` fired in 0/36 scenarios while `RestoreHP` is 24.1 % of
    # live cycles. Its four conjuncts are a combat target, hp < max_hp, a LOSS
    # at current hp and a WIN at max hp — so the cell is a marginal fight, not
    # merely a scratch. Measured at this loadout: `flying_snake` is the farm
    # target and the guard's band is hp 75-85 % of 435, so 348 (0.80) sits in
    # the middle of it rather than on an edge.
    #
    # The band's floor is 75 % because HP_CRITICAL owns everything below
    # `CRITICAL_HP_FRACTION` and preempts this guard outright — the live 50-99 %
    # bucket is therefore split between the two, and this cell is the upper half.
    # D1 derived per §5.3.
    "l22_rest_for_combat": ScenarioCharacter(
        name="l22_rest_for_combat", level=22, hp=348,
        skills={"mining": 20, "woodcutting": 20, "weaponcrafting": 15,
                "gearcrafting": 15, "jewelrycrafting": 15, "cooking": 10,
                "alchemy": 10, "fishing": 10},
        equipment=dict(_IRON_SET), inventory={"cooked_chicken": 6},
        inventory_max=140, bank={"iron_bar": 4}, gold=900,
        derive_combat_stats=True,
        description="Cell 10: 80 % HP against a fight this loadout loses now "
                    "and wins rested — the REST_FOR_COMBAT guard, which no "
                    "scenario could fire before."),

    # --- COVERAGE MATRIX cell 11 (design §5.3): D9 = an UNAFFORDABLE CURRENCY LEAF.
    # `CanIAffordTheCurrencyLeaf`'s positive arm fired in 0/36 scenarios. It
    # needs `analyze_currency_leaves(...).funding_target`, which is set ONLY for
    # a leaf priced in `tasks_coin` at a PERMANENT, LOCATED vendor — and the
    # bundle's four tasks_coin sinks all sit at `tasks_trader`, whose tile is
    # gated on the `tasks_farmer` achievement the capture has NOT completed.
    # Hence `unlocked_achievements`; without it the arm is unreachable from
    # every scenario (see `GameData.from_cache_bundle`).
    #
    # `king_slime_sword` ({iron_bar:8, king_slimeball:6, jasper_crystal:1}) is
    # the only slot behind its target — every other slot is worn at or above its
    # rung-20 candidate, which is what keeps the walk on this root. The bag
    # already holds the iron and the slimeballs, so the actionable step IS the
    # jasper crystal: the exact "stepwise decomposition hands the mapper the
    # currency item directly" shape `_classify_leaves` documents from the live
    # satchel stall of 2026-07-06. Pocket gold is 200 — far under any gold
    # route — so the leaf is unaffordable on both currencies at once.
    # D1 derived per §5.3.
    "l25_currency_leaf_unfunded": ScenarioCharacter(
        name="l25_currency_leaf_unfunded", level=25,
        skills={"mining": 20, "woodcutting": 20, "weaponcrafting": 20,
                "gearcrafting": 20, "jewelrycrafting": 20, "cooking": 10,
                "alchemy": 10, "fishing": 10},
        equipment={
            "weapon_slot": "iron_sword", "helmet_slot": "lucky_wizard_hat",
            "body_armor_slot": "mushmush_jacket",
            "leg_armor_slot": "adventurer_pants",
            "boots_slot": "snakeskin_boots", "ring1_slot": "iron_ring",
            "ring2_slot": "iron_ring", "shield_slot": "slime_shield",
            "amulet_slot": "dreadful_amulet", "artifact1_slot": "novice_guide",
            "artifact2_slot": "lost_world_map",
            "artifact3_slot": "perfect_pearl", "bag_slot": "backpack",
            "rune_slot": "lifesteal_rune",
            "utility1_slot": "greater_health_potion",
            "utility2_slot": "small_health_potion",
        },
        inventory={"iron_bar": 8, "king_slimeball": 6,
                   "greater_health_potion": 6},
        utility_quantities={"utility1_slot": 40, "utility2_slot": 40},
        inventory_max=140, bank={}, gold=200,
        unlocked_achievements=("tasks_farmer",), derive_combat_stats=True,
        description="Cell 11: a jasper-gated weapon with 0 tasks_coin — the "
                    "step IS the currency leaf, so the graph routes to "
                    "ReachCurrency instead of gathering for a craft it cannot "
                    "pay for."),

    # --- COVERAGE MATRIX cell 12 (design §5.3): D11 = a COOKING rung, on a FISHER.
    # Cooking, fishing, alchemy, mining and woodcutting are the five skills the
    # O1 census reports as never ROUTED, and cooking is the one the design named:
    # 33,840 live cooking XP that no node models. `fisher` is a declared role
    # (`role_catalog`: gather fishing, craft cooking), so this character carries
    # its two skills high and everything else at 5.
    #
    # At cooking 21 the grind rung is `cooked_trout` ({trout: 1}) — depth-1 and
    # GATHER-fed, the shape §5.3 packs onto this cell — and with an empty bag and
    # bank the descent lands on `ObtainItem(trout)`, the first FISHING-fed step
    # any scenario produces. Fishing 25 clears the trout spot's level-20 gate, so
    # the flip that makes the cell bite is the ROLE itself: at fishing 5 the same
    # plan has to grind fishing first.
    "l24_fisher_cooking_rung": ScenarioCharacter(
        name="l24_fisher_cooking_rung", level=24,
        skills={"mining": 5, "woodcutting": 5, "weaponcrafting": 5,
                "gearcrafting": 5, "jewelrycrafting": 5, "cooking": 21,
                "alchemy": 5, "fishing": 25},
        equipment=dict(_IRON_SET), inventory={}, inventory_max=130, bank={},
        gold=1200, derive_combat_stats=True,
        description="Cell 12: a fisher-role character standing on a COOKING "
                    "rung — the first scenario whose skill grind descends into "
                    "a fishing gather."),

    # --- COVERAGE MATRIX cell 13 (2026-08-25): the CRAFT_POTIONS guard's
    # BOOST-STOCK arm. `craft_potions_fires` has three arms (unlock-boost
    # `potion_supply.py:184-189`, boost-stock `:210-220`, heal-deficit
    # `:222-225`) and `CraftPotionsGoal._active_craft` has the matching three.
    # Measured over the 42 committed cells: the guard fires in 5 and EVERY ONE
    # takes the heal arm. The boost-stock arm was suite-invisible, and live
    # attribution cannot recover it either (`cycles.action_repr` records the
    # executed action, not the arm that chose it), so the arm's only evidence
    # was a code-read.
    #
    # Its precondition is the heal stock SATISFIED plus an understocked
    # beneficial boost, so the cell is `l20_relief_full_bank`'s loadout with
    # exactly two things changed: utility1_slot carries the level-20 heal
    # baseline (`potion_baseline_pure(20, 5, 5, 45, 100)` == 40) so the heal
    # deficit closes, and the bag holds three units of each earth_boost_potion
    # ingredient so `_recipe_producible` passes and the ladder sizes 3 runs
    # from held stock rather than a 5-run gather batch.
    #
    # THE CELL WAS A DEFECT WITNESS when it landed (55063875) and is now a
    # CONVERGENCE witness — see tests/test_ai/scenarios/test_boost_stock_cell.py.
    # As committed the arm planned `Craft(earth_boost_potion×3)` +
    # `Equip(...→utility1_slot)`, because `craft_ladder._TARGET_SLOT` was the
    # hard-coded string "utility1_slot", so the equip DISPLACED the 40-potion
    # heal stack that is the arm's own precondition while utility2_slot sat
    # empty, and the guard re-fired on the heal arm immediately after.
    # `craft_ladder` now asks `utility_slot.utility_slot_for`, which prefers a
    # FREE slot: the boost lands in utility2_slot, the heal stack survives at
    # 40, and the guard goes silent. The cell keeps utility2_slot EMPTY on
    # purpose — that emptiness is what the free-slot rule is measured against.
    "l20_boost_stock": ScenarioCharacter(
        name="l20_boost_stock", level=20,
        skills={"mining": 20, "woodcutting": 20, "weaponcrafting": 15,
                "gearcrafting": 15, "jewelrycrafting": 15, "cooking": 10,
                "alchemy": 10, "fishing": 10},
        equipment=dict(_IRON_SET) | {"utility1_slot": "small_health_potion"},
        utility_quantities={"utility1_slot": 40},
        inventory={"yellow_slimeball": 3, "sunflower": 3, "algae": 3},
        inventory_max=100, bank={}, gold=1500,
        derive_combat_stats=True,
        description="Cell 13: heal stock AT the level-20 baseline with an "
                    "understocked boost — the only cell that reaches the "
                    "CRAFT_POTIONS guard's boost-stock arm."),
}
