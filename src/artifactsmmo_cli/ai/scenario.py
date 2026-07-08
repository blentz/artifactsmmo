"""Synthetic planner scenarios: a mock character + the real game catalog.

Phase 1 of the progression-tree spec (docs/superpowers/specs/
2026-07-06-progression-tree-design.md): golden scenario tests and the
`plan --scenario` CLI share these fixtures, so a planner change can be
exercised offline against realistic data before it ever runs live."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.game_data import GameData
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
    bank: dict[str, int] | None = field(default_factory=dict)  # None = unknown
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
        equipment=equipment, cooldown_expires=None,
        task_code=task_code, task_type=task_type,
        task_progress=progress, task_total=total,
        task_lifecycle_phase=derive_task_lifecycle_phase(task_code, progress, total),
        bank_items=dict(sc.bank) if sc.bank is not None else None,
        bank_gold=0 if sc.bank is not None else None,
        bank_capacity=200 if sc.bank is not None else None,
        pending_items=None,
        utility1_slot_quantity=sc.utility_quantities.get("utility1_slot", 0),
        utility2_slot_quantity=sc.utility_quantities.get("utility2_slot", 0),
        active_events={code: FAR_FUTURE for code in sc.active_events},
        attack=combat.attack,
        dmg=combat.dmg,
        dmg_elements=combat.dmg_elements,
        resistance=combat.resistance,
        critical_strike=combat.critical_strike,
        initiative=combat.initiative,
    )


def load_bundle_game_data(path: Path) -> GameData:
    return GameData.from_cache_bundle(json.loads(path.read_text()))


_COPPER_SET = {
    "weapon_slot": "copper_dagger", "helmet_slot": "copper_helmet",
    "body_armor_slot": "copper_armor", "leg_armor_slot": "copper_legs_armor",
    "boots_slot": "copper_boots", "ring1_slot": "copper_ring",
    "ring2_slot": "copper_ring",
}

SCENARIOS: dict[str, ScenarioCharacter] = {
    "l1_fresh": ScenarioCharacter(
        name="l1_fresh", level=1, max_hp=120,
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
        description="Band-adequate copper set, empty utility slots, potion mats banked."),
    "l10_weapon_upgrade": ScenarioCharacter(
        name="l10_weapon_upgrade", level=10, max_hp=240,
        skills={"mining": 10, "weaponcrafting": 10},
        equipment={**_COPPER_SET, "weapon_slot": "wooden_stick"},
        bank={"iron_ore": 60, "copper_ore": 20},
        description="Weapon slot lags a tier; upgrade mats banked — gear branch."),
    "l3_low_hp": ScenarioCharacter(
        name="l3_low_hp", level=3, hp=20, max_hp=80,
        description="Critical HP — the survival guard preempts every branch."),
    "l12_taskgated_bag": ScenarioCharacter(
        name="l12_taskgated_bag", level=12, max_hp=260,
        skills={"gearcrafting": 10},
        equipment=dict(_COPPER_SET),
        bank={"cowhide": 5, "feather": 2},
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

    # --- Event-gear pursuit across the L48 wall (2026-07-07 slot-coverage
    # pass): the l48_band_adequate loadout with REAL combat stats
    # (derive_combat_stats — the zero-stat harness default makes every
    # monster unwinnable, so event-gated attainability could never open)
    # and the corrupted_ogre event up. With the event active the L20 ogre
    # (winnable at this loadout) drops corrupted_gem, the permanent
    # cultist_wizard sells corrupted_crown/corrupted_skull for
    # corrupted_gem, and near_term_gear gains event-only candidates
    # (helmet corrupted_crown; artifact2_slot corrupted_skull — RE-DERIVED
    # 2026-07-07 GAP-2 fix: artifact1_slot/artifact3_slot are no longer
    # event-exclusive, perfect_pearl duplicate-fills them regardless of the
    # event once objective._gatherable opens the small_pearls rare-drop
    # route; see test_slot_coverage.py's EVENT_ONLY_CANDIDATES docstring).
    # Artifact slots are deliberately left UNSTOCKED here (unlike
    # l48_band_adequate/l30_rune_fill/l20_dual_utility) so the event's
    # residual artifact2_slot delta stays observable. Without the event the
    # same monsters have no known spawn, the currency leaf stays closed, and
    # (with real stats) the shield/ring2/boots/bag slots also open non-event
    # candidates — so the event-attribution tests compare the WITH/WITHOUT
    # candidate sets on this same state, and the Wait isolation witness
    # stays l48_band_adequate (zero-stat, untouched).
    "l48_event_active": ScenarioCharacter(
        name="l48_event_active", level=48, gold=800,
        skills={"mining": 46, "woodcutting": 46, "weaponcrafting": 42,
                "gearcrafting": 42, "fishing": 42, "cooking": 42,
                "alchemy": 35, "jewelrycrafting": 35},
        equipment={
            "weapon_slot": "mithril_sword", "helmet_slot": "mithril_helm",
            "body_armor_slot": "mithril_platebody", "leg_armor_slot": "mithril_platelegs",
            "boots_slot": "mithril_boots", "ring1_slot": "mithril_ring",
            "ring2_slot": "copper_ring", "amulet_slot": "greater_sapphire_amulet",
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
            "weapon_slot": "iron_dagger", "helmet_slot": "iron_helm",
            "body_armor_slot": "iron_armor", "leg_armor_slot": "iron_legs_armor",
            "boots_slot": "iron_boots", "ring1_slot": "iron_ring",
            "ring2_slot": "iron_ring", "shield_slot": "iron_shield",
            "amulet_slot": "life_amulet",
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
            "weapon_slot": "iron_dagger", "helmet_slot": "adventurer_helmet",
            "body_armor_slot": "adventurer_vest", "leg_armor_slot": "iron_legs_armor",
            "boots_slot": "iron_boots", "ring1_slot": "forest_ring",
            "ring2_slot": "iron_ring", "shield_slot": "iron_shield",
            "amulet_slot": "life_amulet",
            "utility1_slot": "small_health_potion", "utility2_slot": "small_health_potion",
        },
        utility_quantities={"utility1_slot": 20, "utility2_slot": 20},
        bank={"cowhide": 5, "feather": 2},
        derive_combat_stats=True,
        description="L12 twin of l10_bag_pursuit: cow winnable, every other "
                     "slot at its own near_term_gear fixed point (vest, "
                     "helmet, ring1) — satchel is the sole remaining "
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
    # test_l35_artifact_perfect_pearl_targeted_others_closed. The full
    # stack still Waits: perfect_pearl's small_pearls purchase dead-ends at
    # GatherMaterials(small_pearls) (a NEW, distinct gap this fix surfaced
    # — item-currency vendor purchases for a rare-drop leaf don't plan,
    # noted as a follow-up, not fixed by this task), and GAP-6 (old_boots'
    # Fight-drop dead end) is still present underneath, now as a fallback
    # rather than the argmax — see test_slot_coverage.py:
    # test_l35_artifact_fill_full_stack_waits_on_pure_drop_gear.
    "l35_artifact_fill": ScenarioCharacter(
        name="l35_artifact_fill", level=35, gold=300,
        skills={"mining": 32, "woodcutting": 32, "weaponcrafting": 30,
                "gearcrafting": 30, "fishing": 30, "cooking": 30,
                "alchemy": 20, "jewelrycrafting": 20},
        equipment={
            "weapon_slot": "dreadful_staff", "helmet_slot": "piggy_helmet",
            "body_armor_slot": "bandit_armor", "leg_armor_slot": "piggy_pants",
            "boots_slot": "hard_leather_boots", "ring1_slot": "ring_of_the_adept",
            "ring2_slot": "ring_of_the_adept", "amulet_slot": "emerald_amulet",
            "shield_slot": "slime_shield", "bag_slot": "satchel",
            "utility1_slot": "minor_health_potion", "utility2_slot": "minor_health_potion",
        },
        utility_quantities={"utility1_slot": 15, "utility2_slot": 15},
        bank={"gold_ore": 10},
        derive_combat_stats=True,
        description="L35 combat loadout, all three artifact slots empty — "
                     "RE-DERIVED 2026-07-07 (GAP-2 fixed): perfect_pearl "
                     "(small_pearls rare-fishing-drop route) is now the "
                     "argmax artifact target, though the full stack still "
                     "Waits (purchase dead-end, distinct from GAP-6)."),

    # --- Rune slot (deliverable 4). L30 at the near_term_gear fixed point
    # for every other slot (the equip_value argmax set — utility-stat gear
    # included, that IS what the metric converges to), rune_slot EMPTY,
    # alchemy 25 so the stocked minor_health_potion is also the bootstrap
    # target (no utility candidate), and 25000 gold ≥ the 20000
    # lifesteal_rune price at the permanent rune_vendor — the rune IS
    # attainable-now via the gold-purchase leaf and near_term_gear covers
    # rune_slot. LIMITATION (pinned): the chain is INERT past the tree —
    # objective_step_goal routes the recipe-less gold-vendor rune to
    # GatherMaterials(lifesteal_rune), which is unplannable (0 nodes: the
    # rune is neither gatherable nor monster-dropped and the gold NpcBuy
    # path never plans), so the cycle ends in Wait with 25000 gold on
    # hand and the rune one purchase away.
    # ARTIFACT slots stock perfect_pearl (RE-DERIVED 2026-07-07 GAP-2 fix —
    # see l48_band_adequate's comment for the mechanism: perfect_pearl became
    # a real near_term_gear candidate at any level >= 19 once
    # objective._gatherable started reading the full drop set). Restocked so
    # the rune slot stays the SOLE isolated target, per this scenario's
    # documented "every other slot at its own fixed point" methodology.
    "l30_rune_fill": ScenarioCharacter(
        name="l30_rune_fill", level=30, gold=25000,
        skills={"mining": 28, "woodcutting": 28, "weaponcrafting": 25,
                "gearcrafting": 25, "fishing": 25, "cooking": 25,
                "alchemy": 25, "jewelrycrafting": 18},
        equipment={
            "weapon_slot": "mushmush_bow", "helmet_slot": "wolf_ears",
            "body_armor_slot": "bandit_armor", "leg_armor_slot": "piggy_pants",
            "boots_slot": "hard_leather_boots", "ring1_slot": "ring_of_the_adept",
            "ring2_slot": "forest_ring", "amulet_slot": "wisdom_amulet",
            "shield_slot": "iron_shield", "bag_slot": "satchel",
            "artifact1_slot": "perfect_pearl", "artifact2_slot": "perfect_pearl",
            "artifact3_slot": "perfect_pearl",
            "utility1_slot": "minor_health_potion", "utility2_slot": "minor_health_potion",
        },
        utility_quantities={"utility1_slot": 15, "utility2_slot": 15},
        bank={"gold_ore": 5},
        derive_combat_stats=True,
        description="L30, rune_slot empty, 25000 gold for the 20000 "
                     "lifesteal_rune at the permanent rune_vendor — the "
                     "tree arms the rune root but the buy chain is inert "
                     "(pinned Wait)."),

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
            "weapon_slot": "mushmush_bow", "helmet_slot": "wolf_ears",
            "body_armor_slot": "adventurer_vest", "leg_armor_slot": "adventurer_pants",
            "boots_slot": "adventurer_boots", "ring1_slot": "life_ring",
            "ring2_slot": "forest_ring", "amulet_slot": "wisdom_amulet",
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
    # (utility2 gets the catalog's second-best heal) and _utility_candidates
    # skips a slot only when THAT slot's own quantity is stocked — with
    # slot 1 stocked, utility2_slot now arms a real fallback root (it does
    # not win the argmax here; XP still outranks it per GAP-4's design).
    "l20_dual_utility_one_stocked": ScenarioCharacter(
        name="l20_dual_utility_one_stocked", level=20, gold=100,
        skills={"mining": 18, "woodcutting": 18, "weaponcrafting": 15,
                "gearcrafting": 15, "fishing": 15, "cooking": 15,
                "alchemy": 20, "jewelrycrafting": 10},
        equipment={
            "weapon_slot": "mushmush_bow", "helmet_slot": "wolf_ears",
            "body_armor_slot": "adventurer_vest", "leg_armor_slot": "adventurer_pants",
            "boots_slot": "adventurer_boots", "ring1_slot": "life_ring",
            "ring2_slot": "forest_ring", "amulet_slot": "wisdom_amulet",
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
}
