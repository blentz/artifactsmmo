"""Slot-coverage planner net (2026-07-07): event-gear pursuit across the L48
wall plus the never-before-covered equipment slots — bag, artifact1/2/3,
rune, and both utility slots.

Style and seams mirror test_band_liveness (offline seed_offline +
plan_from_state full stack, decide_tree for tree-level assertions), with one
addition: these scenarios run with derive_combat_stats=True, so is_winnable
is judged against REAL loadout stats instead of the zero-stat harness
default under which every monster is unwinnable (see ScenarioCharacter.
derive_combat_stats).

HONEST-OUTCOME RULE: several tests below pin planner behavior that is a
genuine capability GAP, not the desired behavior. Each such pin carries a
LIMITATION comment naming the gap; fixing the gap should FAIL that pin and
force the test (and the report) to be updated — the pins are tripwires,
never endorsements. Gap index:

  GAP-1 (bag, held/banked-stock arm): is_attainable_now's recipe walk has
      no held/banked-stock arm — banked cowhide open nothing for a leaf
      whose only acquisition path (a monster drop) is currently unwinnable,
      even when the bank already holds the full recipe quantity. Pinned at
      the CODE level (test_bag_slot_banked_stock_not_credited): the original
      l10_bag_pursuit framing (cow unwinnable at L10) was retired by the
      2026-07-07 hp-derivation fix wave — cow IS winnable at real L10 hp
      (375), so that scenario no longer demonstrates the gap by itself.
  GAP-2 (artifacts, l35_artifact_fill): no artifact is attainable-now at
      L35; in particular perfect_pearl's small_pearls currency IS a real
      (rare) fishing drop but objective._gatherable consults the PRIMARY
      resource_drops map only, so the archaeologist route reads closed.
  GAP-3 (rune, l30_rune_fill): the tree arms ObtainItem(lifesteal_rune,
      rune_slot) via the gold-purchase leaf, but objective_step_goal routes
      the recipe-less gold-vendor item to GatherMaterials(lifesteal_rune),
      which never plans (dead at 1 node) — the cycle ends in Wait with the gold in
      hand. Vendor-only GOLD-priced equippables are unacquirable.
  GAP-4 (utility, l20_dual_utility): at a band-adequate state the XP
      branch outranks empty utility slots by design (has_structural_upgrade
      deliberately excludes utility) — the utility1 fill only survives as a
      fallback root.
  GAP-5 (utility2, l20_dual_utility_one_stocked): utility_potion_targets
      only ever emits utility1_slot and _utility_candidates drops the
      candidate entirely once the target potion is stocked in ANY slot —
      utility2_slot is unreachable by the tree, full stop.
  GAP-6 (pure-drop dead end, l35_artifact_fill — discovered by the
      2026-07-07 hp-derivation fix wave): a near_term_gear candidate that is
      a recipe-less, non-purchasable, pure MONSTER-DROP item (e.g.
      old_boots) routes through `_equippable_goal` to `UpgradeEquipmentGoal`,
      whose `relevant_actions` drops every Fight action for an unowned,
      uncommitted target — there is no acquisition path at all, so the goal
      dies within a node. When such a candidate OUTRANKS every plannable
      alternative (equip_value's utility-stat weighting, per follow-up #5,
      is large enough to beat even a craftable candidate), the cycle ends in
      Wait with a real, healthy state sitting idle."""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import (
    SCENARIOS,
    ScenarioCharacter,
    load_bundle_game_data,
    scenario_state,
)
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, is_attainable_now
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.scenarios.search_bounds import assert_search_bounded

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

NEW_SCENARIOS = [
    "l48_event_active",
    "l10_bag_pursuit", "l12_bag_pursuit",
    "l35_artifact_fill",
    "l30_rune_fill",
    "l20_dual_utility", "l20_dual_utility_one_stocked",
]

ARTIFACT_SLOTS = {"artifact1_slot", "artifact2_slot", "artifact3_slot"}

EVENT_ONLY_CANDIDATES = {
    "helmet_slot": "corrupted_crown",
    "artifact1_slot": "corrupted_skull",
    "artifact2_slot": "corrupted_skull",
    "artifact3_slot": "corrupted_skull",
}
"""What the corrupted_ogre event adds to l48_event_active's candidate
surface: the L20 ogre (winnable at this loadout) drops corrupted_gem, and
the permanent cultist_wizard sells crown + skull for it — with the event
down those monsters have no known spawn and the currency leaf is closed."""


def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _state(name: str, gd: GameData) -> WorldState:
    return scenario_state(SCENARIOS[name], gd)


def _run(name: str) -> PlanReport:
    gd = load_bundle_game_data(BUNDLE)
    player = GamePlayer(character=name, history=None)
    player.seed_offline(_state(name, gd), gd)
    return player.plan_from_state()


@pytest.mark.parametrize("name", NEW_SCENARIOS)
def test_slot_scenario_registered(name: str) -> None:
    """Registry-first (TDD): the slot-coverage scenarios must exist under
    the exact binding names before anything else in this file can run."""
    assert name in SCENARIOS


@pytest.mark.parametrize("name", NEW_SCENARIOS)
def test_slot_scenario_full_stack_liveness(name: str) -> None:
    """Same liveness contract as the band net: a goal is selected and the
    plan is non-empty (WaitGoal's plan is its Wait action — still
    non-empty; an empty arbitration is a liveness bug regardless)."""
    report = _run(name)
    assert report.selected_goal is not None, (name, report.decision.chosen_root)
    assert report.plan, (
        name, repr(report.selected_goal),
        [g.get("goal") for g in report.goals_tried])


@pytest.mark.parametrize("name", NEW_SCENARIOS)
def test_slot_scenario_search_is_bounded(name: str) -> None:
    """Every tried goal bounded — the shared band-liveness bound."""
    assert_search_bounded(_run(name), name)


# --- Deliverable 1: event-gear pursuit across the L48 wall -----------------

def test_l48_event_candidates_are_event_gated() -> None:
    """The exact candidate delta the corrupted_ogre event buys, measured on
    the SAME state with only the game-data event overlay toggled (the very
    seeding seed_offline performs from state.active_events): with the event
    down the event items are absent; with it up, crown + all three artifact
    slots appear. This is the attribution test — the full-stack test below
    can't distinguish 'event opened the leaf' from 'the leaf was open
    anyway' on its own."""
    gd = _bundle()
    state = _state("l48_event_active", gd)
    objective = CharacterObjective.from_game_data(gd)

    gd.active_event_codes = set()
    without = objective.near_term_gear(state)
    gd.active_event_codes = set(state.active_events)
    with_event = objective.near_term_gear(state)

    for slot, code in EVENT_ONLY_CANDIDATES.items():
        assert with_event.get(slot) == code, (slot, with_event)
        assert without.get(slot) != code, (slot, without)
    # the event only ADDS candidates — the non-event surface is unchanged
    assert {s: c for s, c in with_event.items()
            if s not in EVENT_ONLY_CANDIDATES} == without


def test_l48_event_active_pursues_event_gear() -> None:
    """With the event up the planner must NOT Wait: the event-sourced
    corrupted_crown is the argmax gear candidate (gain 893 vs the mithril
    helm), the chosen root, and the full stack plans the event-monster farm
    for its corrupted_gem currency — the attainability leaf the event
    opened. This is the wall-crossing behavior l48_band_adequate proves
    impossible without events."""
    report = _run("l48_event_active")
    assert report.decision.chosen_root == ObtainItem(
        code="corrupted_crown", quantity=1, slot="helmet_slot")
    assert repr(report.selected_goal) != "Wait", (
        repr(report.selected_goal), report.plan)
    assert repr(report.selected_goal).startswith(
        "GatherMaterials(corrupted_gem"), repr(report.selected_goal)
    assert report.plan and repr(report.plan[0]).startswith(
        "Fight(corrupted_ogre"), report.plan


def test_l48_no_event_witness_still_waits() -> None:
    """Isolation: the l48_band_adequate witness (zero-stat, no events) must
    keep pinning the wall — the planner Waits there. If this ever flips,
    the event-pursuit result above is no longer attributable to the event
    seam and both scenarios must be re-derived.

    NOTE (2026-07-07 hp-derivation fix wave): l48_band_adequate does NOT set
    derive_combat_stats, so this Wait is a SYNTHETIC-hp tripwire (predict_win
    sees 0 attack — every monster is unwinnable by construction, event or
    not), not itself proof of the L48 wall. The real, hp-honest wall claim is
    `test_l48_event_window_monsters_still_unwinnable_with_real_stats` below:
    every L47-50 window monster stays unwinnable even at the true 1570-hp
    mithril loadout. At realistic stats the live planner would NOT sit at
    this Wait — `_pick_winnable_monster()` finds 'goblin_wolfrider' (L40) via
    the xp-fallback arm and grinds L40s toward 50 instead. This test's job is
    narrower: isolating the event-gear pursuit result above from the
    zero-stat harness default, nothing more."""
    report = _run("l48_band_adequate")
    assert repr(report.selected_goal) == "Wait", (
        repr(report.selected_goal), report.plan)
    assert report.decision.chosen_root == ReachCharLevel(level=50)


L47_50_WINDOW_MONSTERS = (
    "duskworm", "dusk_beetle", "sandwarden",
    "desert_scorpion", "solar_desert_scorpion", "baby_red_dragon",
)
"""The FightAction level window [char_level-1, char_level+2] at char_level
48 (`_pick_winnable_monster`'s PREFERRED band) — every non-event monster in
this bundle whose level falls in [47, 50]."""


def test_window_tuple_matches_bundle() -> None:
    """Tripwire for bundle regeneration: L47_50_WINDOW_MONSTERS must be
    EXACTLY the bundle's [47, 50] monster set — a regenerated catalog that
    adds a window monster must not silently escape the wall test below."""
    gd = _bundle()
    window = {code for code, lvl in gd.monster_levels.items() if 47 <= lvl <= 50}
    assert window == set(L47_50_WINDOW_MONSTERS)


def test_l48_event_window_monsters_still_unwinnable_with_real_stats() -> None:
    """The L48 wall is REAL, not a zero-stat harness artifact: even with
    derived (true) mithril-loadout stats (1570 hp), every individual L47-50
    window monster is unwinnable via `is_winnable` — a damage-bound wall, not
    an hp-starvation artifact. The event path is the only one that opens.

    NOTE (2026-07-07 hp-derivation fix wave): `_pick_winnable_monster()` is
    NOT the right assertion here — at realistic hp it returns
    'goblin_wolfrider' (L40), a monster OUTSIDE the L47-50 window, reached via
    the picker's documented xp-fallback arm (any winnable monster still
    granting xp, char_level - monster_level < 10). That is correct picker
    behavior, not a wall breach: the live planner would grind L40s toward 50
    instead of Waiting. The wall claim is scoped to the WINDOW, so it's
    tested per-monster directly against `is_winnable`."""
    gd = load_bundle_game_data(BUNDLE)
    state = _state("l48_event_active", gd)
    for monster in L47_50_WINDOW_MONSTERS:
        assert not is_winnable(state, gd, monster), monster


# --- Deliverable 2: bag slot / satchel chain --------------------------------

def test_bag_slot_banked_stock_not_credited() -> None:
    """GAP-1, pinned at the CODE level (2026-07-07 hp-derivation fix wave):
    is_attainable_now's recipe walk has NO held/banked-stock arm. A minimal
    L1, zero-stat probe character (below any real gear/level story) with the
    satchel's full cowhide requirement (5) ALREADY BANKED still reads
    'cowhide not attainable-now', because the walk only asks 'can I produce
    MORE right now' (cow winnable? gatherable? task-earnable? vendor?) and
    never asks 'do I already hold enough' — the 5 banked cowhide count for
    nothing. This supersedes the old l10_bag_pursuit framing: that scenario
    demonstrated the gap only incidentally, by relying on cow being
    unwinnable at L10 in this bundle — a fact the hp-derivation fix
    overturned (cow IS winnable at real L10 hp, 375). The gap itself is a
    property of is_attainable_now's recipe walk, independent of any
    scenario's winnability threshold, so it is pinned directly against a
    throwaway probe state instead. Fixing the walk to credit held/banked
    stock should FAIL this test."""
    gd = _bundle()
    probe = ScenarioCharacter(
        name="gap1_probe", level=1, max_hp=120, bank={"cowhide": 5},
        description="Throwaway GAP-1 probe: zero-stat L1, cow unwinnable, "
                     "cowhide's full recipe demand already banked.")
    state = scenario_state(probe, gd)
    assert not is_winnable(state, gd, "cow")  # the leaf's only dropper
    assert (state.bank_items or {}).get("cowhide", 0) >= 5  # fully banked
    assert not is_attainable_now("cowhide", state, gd)  # GAP-1, directly
    assert not is_attainable_now("satchel", state, gd)  # propagates upward


def test_l10_bag_pursuit_satchel_live_but_vest_outranks() -> None:
    """Re-derived (2026-07-07 hp-derivation fix wave): the original pin
    ('satchel invisible at L10') was CONTAMINATED — it relied on the
    harness's hand-declared max_hp (240) undershooting the server's real
    115 + 5*level + gear formula (375 at this loadout), which made cow read
    unwinnable. At the real 375 hp cow IS winnable and the satchel chain
    genuinely opens at L10 (GAP-1 does not block it here — the bank stock is
    irrelevant once the monster-drop leaf is winnable on its own).

    The ACTUAL L10 behavior differs from the l12_bag_pursuit twin: at this
    loadout iron_armor (body_armor_slot) is NOT yet a fixed point either —
    adventurer_vest (craftable from the SAME banked cowhide) is also a
    near_term_gear candidate, and outranks bag_slot outright. bag_slot ->
    satchel survives only as a fallback root; the chosen path spends the
    cowhide on the vest instead. l12_bag_pursuit isolates the satchel chain
    in full by pushing every other slot (vest, helmet, ring1) to its own
    fixed point so none of them can compete."""
    gd = _bundle()
    state = _state("l10_bag_pursuit", gd)
    objective = CharacterObjective.from_game_data(gd)
    assert (state.bank_items or {}).get("cowhide", 0) >= 5  # mats really banked
    assert is_winnable(state, gd, "cow")
    assert is_attainable_now("satchel", state, gd)
    assert objective.near_term_gear(state) == {
        "body_armor_slot": "adventurer_vest", "bag_slot": "satchel"}

    report = _run("l10_bag_pursuit")
    assert report.decision.chosen_root == ObtainItem(
        code="adventurer_vest", quantity=1, slot="body_armor_slot")
    assert ObtainItem(code="satchel", quantity=1, slot="bag_slot") \
        in report.decision.fallback_roots
    assert repr(report.selected_goal).startswith("GatherMaterials(cowhide"), (
        repr(report.selected_goal))
    assert report.plan and repr(report.plan[0]).startswith("Fight(cow"), report.plan


def test_l12_bag_pursuit_satchel_chain_live() -> None:
    """The isolation witness that the satchel chain itself works: +2 levels
    flips cow winnable (matching the original minimal-delta framing), and
    every OTHER slot is pushed to its own near_term_gear fixed point (vest,
    helmet, ring1 — re-derived 2026-07-07 hp-derivation fix wave, see
    scenario.py's l12_bag_pursuit comment) so none of them can outrank the
    bag. The tree then targets bag_slot -> satchel as the SOLE candidate.
    The full stack routes the missing task-funded jasper_crystal through the
    C4 funding chain: ReachCurrency(tasks_coin, 8) planning AcceptTask ->
    Fight -> CompleteTask. Together with the L10 pin above (where the vest
    competes and wins) this shows GAP-1's old l10 framing was a scenario
    artifact — the underlying chain itself is healthy end-to-end."""
    gd = _bundle()
    state = _state("l12_bag_pursuit", gd)
    objective = CharacterObjective.from_game_data(gd)
    assert objective.near_term_gear(state) == {"bag_slot": "satchel"}
    assert is_attainable_now("satchel", state, gd)

    report = _run("l12_bag_pursuit")
    assert report.decision.chosen_root == ObtainItem(
        code="satchel", quantity=1, slot="bag_slot")
    assert report.decision.chosen_step == ObtainItem(
        code="jasper_crystal", quantity=1)
    assert repr(report.selected_goal).startswith("ReachCurrency(tasks_coin"), (
        repr(report.selected_goal))
    assert report.plan and repr(report.plan[0]).startswith("AcceptTask"), report.plan


# --- Deliverable 3: artifact slots ------------------------------------------

def test_l35_artifact_slots_never_targeted() -> None:
    """LIMITATION (GAP-2, pinned): with all three artifact slots EMPTY at
    L35, the tree's candidate surface contains NO artifact slot — every
    artifact in the bundle is a recipe-less vendor purchase whose currency
    leaf is closed at this tier (lich/rosenblood/cultist_emperor unwinnable;
    corrupted_gem event-gated; novice_guide has no acquisition path at
    all). The planner chases equip_value utility gear instead. Empty
    artifact slots are simply invisible at L35."""
    gd = _bundle()
    state = _state("l35_artifact_fill", gd)
    objective = CharacterObjective.from_game_data(gd)
    for slot in ARTIFACT_SLOTS:
        assert state.equipment[slot] is None  # scenario construction
    targets = objective.near_term_gear(state)
    assert not (set(targets) & ARTIFACT_SLOTS), targets
    artifacts = [code for code, stats in gd.all_item_stats.items()
                 if stats.type_ == "artifact"]
    assert artifacts  # the bundle really has artifacts to miss
    for code in artifacts:
        assert not is_attainable_now(code, state, gd), code


def test_l35_artifact_small_pearls_primary_map_gap() -> None:
    """The sharpest edge of GAP-2: perfect_pearl (L20 artifact, permanent
    archaeologist vendor, 20 small_pearls) SHOULD be reachable — small_pearls
    is a real gatherable, dropped (rarely) by the trout/bass/salmon fishing
    spots this character can already work (fishing 30). It reads
    unattainable only because objective._gatherable consults the PRIMARY
    resource_drops map, which keeps one drop per resource; the full drop
    table (gatherable_drop_items — grown for exactly this reason, see its
    docstring's gem-stone note) knows better. Fixing _gatherable to use the
    full table should FAIL this test's last assertion."""
    gd = _bundle()
    state = _state("l35_artifact_fill", gd)
    assert "small_pearls" in gd.gatherable_drop_items()      # truly gatherable
    assert "small_pearls" not in set(gd.resource_drops.values())  # primary-map blind
    assert not is_attainable_now("perfect_pearl", state, gd)  # the consequence


def test_l35_artifact_fill_full_stack_waits_on_pure_drop_gear() -> None:
    """LIMITATION (GAP-6, discovered by the 2026-07-07 hp-derivation fix
    wave, pinned): at real 915 hp the argmax gear candidate flips from
    mushmush_bow (a CRAFTED weapon blocked only on task-funded jasper_crystal
    — the chain that used to fire here) to old_boots — a level-20, PURE
    monster-drop boots item (recipe=None, no permanent vendor) with no
    combat value of its own (hp_bonus 90 / wisdom 70 / prospecting 20) that
    only outranks everything else via equip_value's utility-stat weighting
    (same inflation effect noted for mushmush_bow/wolf_ears in the project
    report's follow-up #5 — now strong enough to beat a CRAFTABLE candidate
    outright, not just a combat-tier one). is_attainable_now says True (its
    dropper, spider, is winnable at this hp), so near_term_gear offers it —
    but `_equippable_goal` routes an unowned, recipe-less, non-purchasable
    target straight to `UpgradeEquipmentGoal`, whose `relevant_actions`
    drops EVERY Fight action for an uncommitted acquisition (progression.py
    ~line 251: 'Everything else (Fight, ...) is irrelevant to
    building+equipping the target'). There is no GOAP path from 'need to
    fight for old_boots' to 'wearing old_boots' at all, so the goal plans to
    0 nodes and every other near_term_gear candidate here (wolf_ears: same
    pure-drop dead end; wisdom_amulet: pre-existing green_cloth craft gap,
    unrelated) is equally inert — the cycle ends in Wait. This is the
    monster-drop counterpart of GAP-1 (bag): a pure-drop equippable that
    OUTRANKS a plannable candidate is worse than invisible, it's a silent
    dead end. Wiring a Fight-to-acquire arm into `_equippable_goal` for
    unowned pure-drop targets should FAIL this pin (Wait -> a working gear
    chain, most likely the old mushmush_bow/ReachCurrency(tasks_coin) path)."""
    report = _run("l35_artifact_fill")
    assert report.decision.chosen_root == ObtainItem(
        code="old_boots", quantity=1, slot="boots_slot")
    assert repr(report.selected_goal) == "Wait", (
        repr(report.selected_goal), report.plan)


# --- Deliverable 4: rune slot ------------------------------------------------

def test_l30_rune_candidate_armed() -> None:
    """The GOOD half: near_term_gear covers rune_slot. With 25000 gold
    against the permanent rune_vendor's 20000 lifesteal_rune, the
    gold-purchase leaf opens and the empty rune slot gets its candidate —
    the tree-level slot coverage the fixed-point loadout isolates (every
    other slot is already at its argmax, so the rune is the sole target)."""
    gd = _bundle()
    state = _state("l30_rune_fill", gd)
    objective = CharacterObjective.from_game_data(gd)
    assert objective.near_term_gear(state) == {"rune_slot": "lifesteal_rune"}
    assert is_attainable_now("lifesteal_rune", state, gd)


def test_l30_rune_chain_inert_waits() -> None:
    """LIMITATION (GAP-3, pinned): past the tree, the rune chain is INERT.
    decide_tree promotes ObtainItem(lifesteal_rune, rune_slot) to chosen
    root, but objective_step_goal/_equippable_goal routes the recipe-less
    gold-vendor item to GatherMaterials(lifesteal_rune) — item-currency
    purchases get the incremental fund-and-buy treatment there, GOLD-priced
    ones are documented to 'fall through to the buy attempt', and that buy
    attempt never plans (0 nodes: the rune is neither gatherable nor
    monster-dropped and no NpcBuy path fires). The cycle ends in Wait with
    the full purchase price in hand and the rune one buy away. Wiring a
    gold NpcBuy path should FAIL this test (Wait -> a buy/equip goal)."""
    report = _run("l30_rune_fill")
    assert report.decision.chosen_root == ObtainItem(
        code="lifesteal_rune", quantity=1, slot="rune_slot")
    rune_entries = [g for g in report.goals_tried
                    if str(g.get("goal", "")).startswith("GatherMaterials(lifesteal_rune")]
    assert rune_entries, report.goals_tried
    assert all(entry["nodes"] == 0 for entry in rune_entries), rune_entries
    assert repr(report.selected_goal) == "Wait", (
        repr(report.selected_goal), report.plan)


# --- Deliverable 5: both utility slots ---------------------------------------

def test_l20_dual_utility_xp_outranks_empty_utility() -> None:
    """LIMITATION (GAP-4, pinned): both utility slots EMPTY, the bootstrap
    target (minor_health_potion, alchemy 20) craftable with banked mats —
    and the FIRST decision is still the trunk grind, not utility1.
    has_structural_upgrade deliberately excludes utility candidates (its
    docstring: consumable restock must never break adequacy), so a
    band-adequate state sends the XP branch first and the utility fill
    survives only as THE fallback root. Empty utility slots therefore fill
    opportunistically (when the trunk step yields no goal), never as the
    primary decision. If utility provisioning is ever promoted, this pin
    flips."""
    report = _run("l20_dual_utility")
    assert report.decision.chosen_root == ReachCharLevel(level=30)
    assert report.decision.fallback_roots == [ObtainItem(
        code="minor_health_potion", quantity=1, slot="utility1_slot")]
    assert repr(report.selected_goal).startswith("GrindCharacterXP"), (
        repr(report.selected_goal))


def test_l20_one_stocked_utility2_never_targeted() -> None:
    """LIMITATION (GAP-5, pinned): stock utility1 with the target potion and
    the second utility slot becomes UNREACHABLE — utility_potion_targets
    only ever emits utility1_slot, and _utility_candidates drops the
    candidate entirely once equipped_potion_qty(target) > 0 anywhere. The
    decision carries NO utility root at all (chosen or fallback): utility2
    stays empty until utility1 is fully consumed. Proving BOTH slots get
    filled is exactly what the tree cannot do today; emitting a
    utility2_slot target should FAIL this test."""
    gd = _bundle()
    state = _state("l20_dual_utility_one_stocked", gd)
    objective = CharacterObjective.from_game_data(gd)
    # the target is stocked in slot 1, slot 2 is empty
    assert state.equipment["utility1_slot"] == "minor_health_potion"
    assert state.equipment["utility2_slot"] is None
    assert objective.utility_potion_targets(state) == {
        "utility1_slot": "minor_health_potion"}  # slot-2 never even named

    report = _run("l20_dual_utility_one_stocked")
    assert report.decision.chosen_root == ReachCharLevel(level=30)
    assert report.decision.fallback_roots == []
    all_reprs = [repr(r) for r in (
        report.decision.chosen_root, report.decision.chosen_step,
        *report.decision.fallback_roots, *report.decision.fallback_steps)]
    assert not any("utility2_slot" in r for r in all_reprs), all_reprs
    assert repr(report.selected_goal).startswith("GrindCharacterXP"), (
        repr(report.selected_goal))
