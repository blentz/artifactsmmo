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

  GAP-1 (bag, held/banked-stock arm) — FIXED 2026-07-07: is_attainable_now's
      recipe walk now short-circuits on held/banked stock (mirrors
      strategy._producible's held-stock arm) — banked cowhide credits
      attainability even when the leaf's only acquisition path (a monster
      drop) is currently unwinnable, and a banked CRAFTED item short-circuits
      its own recipe walk. Pinned at the CODE level
      (test_bag_slot_banked_stock_credited): the original l10_bag_pursuit
      framing (cow unwinnable at L10) was retired by the 2026-07-07
      hp-derivation fix wave — cow IS winnable at real L10 hp (375), so that
      scenario no longer demonstrates the gap by itself.
  GAP-2 (artifacts, l35_artifact_fill) — FIXED 2026-07-07: objective._gatherable
      now consults the FULL drop set (`gatherable_drop_items()`, not just the
      primary `resource_drops` map), so a rare secondary drop like
      small_pearls (off trout/bass/salmon fishing spots) reads gatherable and
      perfect_pearl's archaeologist-vendor route opens. Pinned at the CODE
      level (test_l35_artifact_small_pearls_gatherable_via_full_drop_set) AND
      at the scenario level: l35_artifact_fill's empty artifact slots NOW
      target perfect_pearl (test_l35_artifact_perfect_pearl_targeted_others_
      closed) — the fix's blast radius reaches every scenario in this bundle
      with an empty artifact slot at level >= 19 (perfect_pearl's equip_value,
      201, all `prospecting`, is high enough to duplicate-fill all three
      artifact slots outright); scenarios NOT under test for artifact
      candidacy were re-fixed-pointed by stocking perfect_pearl in
      scenario.py (mirrors the earlier hp-derivation fix wave's wolf_ears/
      mushmush_bow re-iteration) — see scenario.py's l48_band_adequate/
      l30_rune_fill/l20_dual_utility* comments. l48_event_active was left
      unstocked (its EVENT_ONLY_CANDIDATES table narrowed instead — the
      event's artifact-slot delta is now only artifact2_slot, see that
      constant's docstring). The FOLLOW-UP this fix surfaced —
      perfect_pearl's small_pearls purchase attainable-now yet UNPLANNABLE
      (`GatherMaterials(small_pearls, ...)` dead at 1 node/0-length plan,
      the same shape GAP-3 documents for gold-priced purchases, but for an
      ITEM-currency purchase) — was GAP-7, FIXED 2026-07-08 (see below).
  GAP-3 (rune, l30_rune_fill) — FIXED 2026-07-08: gold is not an inventory
      item. `analyze_currency_leaves` judged a gold-priced buy leaf's
      affordability from `inventory["gold"] + bank_items["gold"]` — always
      0, whatever `state.gold` held — so GatherMaterialsGoal.is_plannable
      pruned GatherMaterials(lifesteal_rune) before the search started
      (the pinned 0-node dead end) with the full 25000-gold purchase price
      in state.gold. The gold arm now reads `state.gold + bank_gold`
      (None-safe: an UNKNOWN bank credits nothing, mirroring the GAP-1
      bank-stock rule), and `relevant_actions` admits a deficit-sized
      WithdrawGold edge when the pocket alone is short but pocket+bank
      covers (admit/emit symmetry: NpcBuyAction's gold gate is
      POCKET-only, so the plan chains WithdrawGold -> NpcBuy). Pinned
      positively (test_l30_rune_gold_buy_chain_plans): the cycle plans
      NpcBuy(lifesteal_rune) instead of Wait. NOTE: an UNAFFORDABLE gold
      price still defers honestly (blocked, no funding root — gold
      grinding as a tree-funded root is a design extension, see the GAP-3
      report's follow-ups).
  GAP-4 (utility, l20_dual_utility): at a band-adequate state the XP
      branch outranks empty utility slots by design (has_structural_upgrade
      deliberately excludes utility) — both utility fills only survive as
      fallback roots (widened 2026-07-07 by the GAP-5 fix below: both slots
      now produce a candidate, so the fallback list carries two entries
      instead of one — the XP-outranks verdict itself is UNCHANGED design).
  GAP-5 (utility2, l20_dual_utility_one_stocked) — FIXED 2026-07-07:
      `utility_potion_targets` now emits BOTH utility1_slot (the effect-best
      craftable-now heal, unchanged) and utility2_slot (the catalog's
      SECOND-best heal, via `bootstrap_potion_target`'s new `exclude`
      parameter — same-code dual utility slots are not server-legal, see
      actions/equip.py's DUPLICATE_SLOT_TYPES comment), and
      `_utility_candidates` skips a slot only when THAT slot's own quantity
      is stocked (`state.utility1_slot_quantity`/`utility2_slot_quantity`),
      not `equipped_potion_qty`'s any-slot sum. Pinned at the CODE level
      (test_l20_one_stocked_utility2_now_targeted, renamed from
      ..._never_targeted) and the tree level: with utility1 stocked, slot 2
      now arms a real fallback root. equipped_potion_qty ITSELF is
      unchanged — other consumers (guard/goal provisioning) still rely on
      its any-slot sum.
  GAP-6 (pure-drop dead end, l35_artifact_fill — discovered by the
      2026-07-07 hp-derivation fix wave) — FIXED 2026-07-08: a near_term_gear
      candidate that is a recipe-less, non-purchasable, pure MONSTER-DROP
      item (old_boots, sole dropper spider) routes through `_equippable_goal`
      to `UpgradeEquipmentGoal`, whose `relevant_actions` used to drop every
      Fight action — no acquisition edge at all, the goal died within a node
      and the cycle Waited with a healthy character. `relevant_actions` now
      mirrors GatherMaterialsGoal's proven dropper wiring
      (select_monster_for_drop core, Formal/MonsterDropSelection.lean) for
      the goal's OWN target item: the expected-kills-optimal WINNABLE
      dropper's FightAction is emitted — plain when xp-positive, as the
      drop_farm variant (proven xp-gate bypass,
      Formal/ActionApplicability.lean dropFarm arm) when grey — plus a
      synthesized Equip leg for the unowned recipe-less target (the factory
      only enumerates equips for craftable/owned items). grey_farm_allowed
      is deliberately NOT consulted for the goal's own equip target: that
      policy's next-tier suppression assumes the substitute grind is armed
      by the suppressed recipe's own family, which holds for materials but
      not for equip targets (l35 witness: enchanter_boots crafts at
      gearcrafting 35 vs skill 30, within margin, yet nothing arms that
      grind — suppression would re-create the Wait livelock). Pinned
      positively at the scenario level — since the GAP-7 fix un-demoted
      old_boots in l35_artifact_fill, the coverage lives in the
      pearl-stocked variant (l35_boots_drop_farm,
      test_l35_boots_drop_farm_fights_grey_dropper) — and the unit
      level (test_upgrade_slot_lock.py's TestTargetDropFights).
  GAP-7 (secondary-drop blindness in the GOAP gather layer,
      l35_artifact_fill) — FIXED 2026-07-08: `recipe_closure` fed
      `needed_resources` from the primary `resource_drops` map only (one
      rate-best drop per resource), so a rare SECONDARY drop like
      small_pearls marked no resource as needed and GatherMaterialsGoal
      filtered out the action factory's targeted secondary-drop gathers
      (which existed all along — P1 rare multi-drop targeting). The
      goal-layer analog of GAP-2, fixed the same way one layer down: the
      wrapper unions the pure core's `needed_resources` across the
      secondary-drop layers of `resource_drops_full` (input construction —
      the proven core, its Lean mirror and the diff harness are untouched;
      see recipe_closure._secondary_drop_layers). Pinned at the scenario
      level (test_l35_artifact_fill_pearl_route_plans: the former 1-node
      dead search now plans Gather(bass_spot->small_pearls)) and the unit
      level (test_recipe_closure.py's secondary-drop tests)."""

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
    "l35_artifact_fill", "l35_boots_drop_farm",
    "l30_rune_fill",
    "l20_dual_utility", "l20_dual_utility_one_stocked",
]

ARTIFACT_SLOTS = {"artifact1_slot", "artifact2_slot", "artifact3_slot"}

EVENT_ONLY_CANDIDATES = {
    "helmet_slot": "corrupted_crown",
    "artifact2_slot": "corrupted_skull",
}
"""What the corrupted_ogre event adds to l48_event_active's candidate
surface: the L20 ogre (winnable at this loadout) drops corrupted_gem, and
the permanent cultist_wizard sells crown + skull for it — with the event
down those monsters have no known spawn and the currency leaf is closed.

RE-DERIVED 2026-07-07 (GAP-2 fix): artifact1_slot/artifact3_slot dropped
from this table. perfect_pearl (equip_value 201 — the small_pearls rare-
fishing-drop route GAP-2 opened) now ranks #1 among attainable-now
artifacts EVEN WITHOUT the event, and DUPLICATE_SLOT_TYPES fills the extra
artifact slots by repeating the best attainable item — so artifact1_slot
and artifact3_slot both read perfect_pearl in the WITHOUT-event state too
(`_slot_assignments` duplicate-fill), no longer an event-exclusive delta.
corrupted_skull (value 17, event-only) still displaces perfect_pearl at
the SECOND ranked position (`_slot_assignments`' index-1 slot,
artifact2_slot) whenever it is attainable — the narrower, but still real,
event-attributable artifact-slot candidate that survives the fix."""


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
    down the event items are absent; with it up, crown appears and
    corrupted_skull outranks perfect_pearl at artifact2_slot (RE-DERIVED
    2026-07-07, GAP-2 fix: artifact1_slot/artifact3_slot are no longer
    event-exclusive, see EVENT_ONLY_CANDIDATES's docstring). This is the
    attribution test — the full-stack test below can't distinguish 'event
    opened the leaf' from 'the leaf was open anyway' on its own."""
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
    # the event only CHANGES the EVENT_ONLY_CANDIDATES slots — every other
    # slot's candidate is unaffected by the toggle (compare both sides with
    # those slots excluded, since a slot can have a real non-event default
    # candidate the event candidate outranks, not merely an absent one).
    excluded = set(EVENT_ONLY_CANDIDATES)
    assert {s: c for s, c in with_event.items() if s not in excluded} == \
           {s: c for s, c in without.items() if s not in excluded}


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

def test_bag_slot_banked_stock_credited() -> None:
    """GAP-1, FIXED 2026-07-07: is_attainable_now's recipe walk now has a
    held/banked-stock short-circuit (mirrors strategy._producible). A
    minimal L1, zero-stat probe character (below any real gear/level story,
    both cow AND chicken unwinnable to it — cowhide and feather's only
    droppers) with satchel's cowhide (5) AND feather (2) requirements ALREADY
    BANKED (the third material, jasper_crystal, is independently
    task-earnable — the C4 funding loop is always available) reads both
    materials, and satchel itself, attainable-now via the stock credit alone
    — the walk no longer only asks 'can I produce MORE right now' (cow/
    chicken winnable? gatherable? task-earnable? vendor?); it first asks 'do
    I already hold enough', and the banked stock answers yes for both. This
    supersedes the old l10_bag_pursuit framing: that scenario demonstrated
    the (now-fixed) gap only incidentally, by relying on cow being
    unwinnable at L10 in this bundle — a fact the hp-derivation fix
    overturned (cow IS winnable at real L10 hp, 375). The fix itself is a
    property of is_attainable_now's recipe walk, independent of any
    scenario's winnability threshold, so it is pinned directly against a
    throwaway probe state instead."""
    gd = _bundle()
    probe = ScenarioCharacter(
        name="gap1_probe", level=1, max_hp=120, bank={"cowhide": 5, "feather": 2},
        description="Throwaway GAP-1 probe: zero-stat L1, cow+chicken "
                     "unwinnable, satchel's cowhide+feather recipe demand "
                     "already banked.")
    state = scenario_state(probe, gd)
    assert not is_winnable(state, gd, "cow")      # cowhide's only dropper
    assert not is_winnable(state, gd, "chicken")  # feather's only dropper
    assert (state.bank_items or {}).get("cowhide", 0) >= 5  # fully banked
    assert (state.bank_items or {}).get("feather", 0) >= 2  # fully banked
    assert is_attainable_now("cowhide", state, gd)  # GAP-1 fix, directly
    assert is_attainable_now("feather", state, gd)  # GAP-1 fix, directly
    assert is_attainable_now("satchel", state, gd)  # propagates upward


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

def test_l35_artifact_perfect_pearl_targeted_others_closed() -> None:
    """RE-DERIVED 2026-07-07 (GAP-2 FIXED): with all three artifact slots
    EMPTY at L35, the tree's candidate surface now DOES contain an
    artifact — perfect_pearl. Its currency, small_pearls, is a rare
    trout/bass/salmon fishing-spot drop that `objective._gatherable` used
    to miss (primary-drop-map only); now reading the full drop set
    (`gatherable_drop_items()`), it opens the archaeologist-vendor route.
    At equip_value 201 (all `prospecting`) perfect_pearl duplicate-fills
    all three artifact slots (DUPLICATE_SLOT_TYPES). Every OTHER artifact
    in the bundle stays closed at this tier for its own, unrelated reason —
    GAP-2's fix is narrow, opening exactly the one rare-drop route it
    targets, not every artifact: lich/rosenblood/cultist_emperor (their
    vendor currencies) are unwinnable; corrupted_gem is event-gated;
    novice_guide has no acquisition path at all."""
    gd = _bundle()
    state = _state("l35_artifact_fill", gd)
    objective = CharacterObjective.from_game_data(gd)
    for slot in ARTIFACT_SLOTS:
        assert state.equipment[slot] is None  # scenario construction
    targets = objective.near_term_gear(state)
    assert {slot: targets[slot] for slot in ARTIFACT_SLOTS if slot in targets} == {
        slot: "perfect_pearl" for slot in ARTIFACT_SLOTS}
    artifacts = [code for code, stats in gd.all_item_stats.items()
                 if stats.type_ == "artifact"]
    assert artifacts  # the bundle really has artifacts to miss
    assert {code for code in artifacts if is_attainable_now(code, state, gd)} == {
        "perfect_pearl"}


def test_l35_artifact_small_pearls_gatherable_via_full_drop_set() -> None:
    """GAP-2 FIXED, 2026-07-07: perfect_pearl (L20 artifact, permanent
    archaeologist vendor, 20 small_pearls) is reachable — small_pearls is a
    real gatherable, dropped (rarely) by the trout/bass/salmon fishing spots
    this character can already work (fishing 30). `objective._gatherable`
    now consults the FULL drop table (`gatherable_drop_items()`, grown for
    exactly this reason — see its docstring's gem-stone note), not just the
    primary `resource_drops` map (which keeps one drop per resource and was
    blind to small_pearls). small_pearls itself is a leaf (gatherable is
    state-independent) so `is_attainable_now` needs no affordability check
    for it; perfect_pearl's currency-recursion arm then finds that leaf and
    opens the vendor route."""
    gd = _bundle()
    state = _state("l35_artifact_fill", gd)
    assert "small_pearls" in gd.gatherable_drop_items()      # truly gatherable
    assert "small_pearls" not in set(gd.resource_drops.values())  # primary-map blind
    assert is_attainable_now("small_pearls", state, gd)       # the fixed leaf
    assert is_attainable_now("perfect_pearl", state, gd)      # propagates upward


def test_l35_artifact_fill_pearl_route_plans() -> None:
    """GAP-7 FIXED (2026-07-08) — the former tripwire
    (test_l35_artifact_fill_pure_drop_gear_farms_dropper's nodes==1 /
    plan_len==0 pin), rewritten positive. The derivation up to the step is
    UNCHANGED from the GAP-2/GAP-3/GAP-6 re-derivations:

    - chosen_root is still perfect_pearl (equip_value 201 artifact,
      duplicate-fills all three empty artifact slots, outranks old_boots —
      which stays in the fallback list, now never reached).

    NEW: perfect_pearl's step is no longer dead. `recipe_closure` unions
    the secondary-drop layers of `resource_drops_full` into
    `needed_resources` (one proven pure-core run per layer — the input-
    construction fix; the core itself is untouched), so
    `GatherMaterials(small_pearls, {small_pearls:1})` now admits the action
    factory's targeted secondary-drop gathers
    (`GatherAction(drop_item_override='small_pearls')` — those existed all
    along, P1 rare multi-drop targeting; the goal's primary-map blindness
    filtered them out). Derived plan, no skill prereq needed: fishing 30
    opens trout_spot (20) and bass_spot (30); salmon_spot (40) — the
    rate-best pearl source at 1/100 — is dropped by the admission's
    _skill_open gate (skills are immutable in-plan, so a skill-closed
    source can never fire; unchecked it would WIN the yield narrowing and
    kill the plan). Between the two open spots the effective-drop yield
    narrowing (select_gather_source, GatherSelection.lean) breaks the
    300-rate tie on distance — bass_spot's nearest tile is 18 from spawn
    (0,0) vs trout_spot's 19 — leaving ONE admitted gather. One sim-gather
    credits one unit (the deliberate drop_item_override abstraction), so
    the whole step is the single action Gather(bass_spot->small_pearls):
    2 nodes / 1-length plan, replacing the 1-node dead search. The demotion
    chain to old_boots therefore never fires here; its GAP-6 drop-farm
    coverage lives on in the pearl-stocked variant
    (test_l35_boots_drop_farm_fights_grey_dropper below)."""
    report = _run("l35_artifact_fill")
    assert report.decision.chosen_root == ObtainItem(
        code="perfect_pearl", quantity=1, slot="artifact1_slot")
    assert ObtainItem(code="old_boots", quantity=1, slot="boots_slot") \
        in report.decision.fallback_roots
    small_pearls_entries = [g for g in report.goals_tried if str(g.get("goal", ""))
                            .startswith("GatherMaterials(small_pearls")]
    assert small_pearls_entries, report.goals_tried
    assert all(entry["nodes"] == 2 and entry["plan_len"] == 1
               for entry in small_pearls_entries), small_pearls_entries  # GAP-7 flip
    assert repr(report.selected_goal).startswith("GatherMaterials(small_pearls"), (
        repr(report.selected_goal), report.plan)
    assert [repr(a) for a in report.plan] == ["Gather(bass_spot->small_pearls)"], \
        report.plan
    assert report.plan[0].drop_item_override == "small_pearls"


def test_l35_boots_drop_farm_fights_grey_dropper() -> None:
    """GAP-6 coverage keeper (2026-07-08) — split out of the l35 test when
    the GAP-7 fix made the pearl route plan (which un-demoted old_boots).
    Same loadout with the three artifact slots pearl-STOCKED
    (l35_boots_drop_farm; perfect_pearl is prospecting-only, combat stats
    unchanged), so the pearl route is already done and old_boots — a
    level-20, recipe-less, non-purchasable, pure monster-drop boots item —
    is now the CHOSEN root, not a demotion target. `_equippable_goal`
    routes it to UpgradeEquipmentGoal(committed=(old_boots, boots_slot))
    whose `relevant_actions` emits the target's winnable dropper: spider
    (L20, the sole dropper, winnable at this loadout) is grey at L35
    (xp_per_kill == 0, 15 levels down), so the fight arrives as the
    drop_farm variant (proven xp-gate bypass) plus the synthesized
    Equip(old_boots->boots_slot) leg. The cycle plans Fight(spider) ->
    Equip instead of Wait — a healthy character still never idles on a
    farmable upgrade."""
    report = _run("l35_boots_drop_farm")
    assert report.decision.chosen_root == ObtainItem(
        code="old_boots", quantity=1, slot="boots_slot")
    assert repr(report.selected_goal).startswith("UpgradeEquipment"), (
        repr(report.selected_goal), report.plan)
    assert report.plan, report.goals_tried
    fights = [a for a in report.plan if repr(a) == "Fight(spider)"]
    assert fights and all(a.drop_farm for a in fights), report.plan
    assert any(repr(a) == "Equip(old_boots->boots_slot)" for a in report.plan), \
        report.plan


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


def test_l30_rune_gold_buy_chain_plans() -> None:
    """GAP-3 FIXED (2026-07-08) — the former tripwire, rewritten positive.
    Same scenario, new expectation: decide_tree still promotes
    ObtainItem(lifesteal_rune, rune_slot) to chosen root and
    objective_step_goal/_equippable_goal still routes the recipe-less
    gold-vendor rune to GatherMaterials(lifesteal_rune) — but the gold arm
    in analyze_currency_leaves now reads state.gold (+known bank_gold), so
    with 25000 >= the 20000 price the goal is plannable and the search
    finds the one-step buy: NpcBuy(lifesteal_rune×1@rune_vendor) (movement
    to the vendor folds into NpcBuyAction.apply; the equip is the NEXT
    cycle's stepwise leg, per the one-leg-per-cycle idiom). The cycle no
    longer Waits with the purchase price in hand."""
    report = _run("l30_rune_fill")
    assert report.decision.chosen_root == ObtainItem(
        code="lifesteal_rune", quantity=1, slot="rune_slot")
    assert repr(report.selected_goal).startswith(
        "GatherMaterials(lifesteal_rune"), (
        repr(report.selected_goal),
        [g.get("goal") for g in report.goals_tried])
    assert report.plan and any(
        repr(a).startswith("NpcBuy(lifesteal_rune") for a in report.plan
    ), report.plan


# --- Deliverable 5: both utility slots ---------------------------------------

def test_l20_dual_utility_xp_outranks_empty_utility() -> None:
    """LIMITATION (GAP-4, pinned — DESIGNED, not a bug): both utility slots
    EMPTY, the bootstrap target (minor_health_potion, alchemy 20) craftable
    with banked mats, and the catalog's second-best (small_health_potion,
    alchemy 5) also craftable now — and the FIRST decision is still the
    trunk grind, not either utility slot. has_structural_upgrade
    deliberately excludes utility candidates (its docstring: consumable
    restock must never break adequacy), so a band-adequate state sends the
    XP branch first and BOTH utility fills survive only as fallback roots,
    in pick order (minor_health_potion/utility1 first — bigger gain — then
    small_health_potion/utility2). RE-DERIVED 2026-07-07 by the GAP-5 fix:
    the fallback list now carries two entries instead of one (utility2 is
    reachable — see test_l20_one_stocked_utility2_now_targeted below), but
    the XP-outranks-empty-utility verdict this test exists to pin is
    UNCHANGED. Empty utility slots therefore fill opportunistically (when
    the trunk step yields no goal), never as the primary decision. If
    utility provisioning is ever promoted, this pin flips."""
    report = _run("l20_dual_utility")
    assert report.decision.chosen_root == ReachCharLevel(level=30)
    assert report.decision.fallback_roots == [
        ObtainItem(code="minor_health_potion", quantity=1, slot="utility1_slot"),
        ObtainItem(code="small_health_potion", quantity=1, slot="utility2_slot"),
    ]
    assert repr(report.selected_goal).startswith("GrindCharacterXP"), (
        repr(report.selected_goal))


def test_l20_one_stocked_utility2_now_targeted() -> None:
    """GAP-5 FIXED 2026-07-07 (renamed from ..._never_targeted, whose
    LIMITATION pin this flips): stock utility1 with the bootstrap target and
    utility2 is now REACHABLE. utility_potion_targets emits BOTH slots
    unconditionally (utility1: the effect-best craftable-now heal,
    minor_health_potion; utility2: the catalog's SECOND-best,
    small_health_potion, via bootstrap_potion_target's new `exclude`
    parameter — same-code dual utility slots are not server-legal).
    _utility_candidates then applies the PER-SLOT stock check: utility1's
    own quantity (15, from the scenario) is > 0 so its candidate is skipped
    (churn guard intact — a stocked slot is never re-targeted), while
    utility2's own quantity (0) is not, so its candidate survives into the
    decision as a fallback root (XP still outranks it here per GAP-4's
    design — the band is adequate and structural candidates are empty, so
    the trunk is chosen; the utility2 candidate is real but does not win
    the argmax in this scenario)."""
    gd = _bundle()
    state = _state("l20_dual_utility_one_stocked", gd)
    objective = CharacterObjective.from_game_data(gd)
    # the target is stocked in slot 1, slot 2 is empty
    assert state.equipment["utility1_slot"] == "minor_health_potion"
    assert state.equipment["utility2_slot"] is None
    assert objective.utility_potion_targets(state) == {
        "utility1_slot": "minor_health_potion",
        "utility2_slot": "small_health_potion",
    }

    report = _run("l20_dual_utility_one_stocked")
    assert report.decision.chosen_root == ReachCharLevel(level=30)
    assert report.decision.fallback_roots == [ObtainItem(
        code="small_health_potion", quantity=1, slot="utility2_slot")]
    all_reprs = [repr(r) for r in (
        report.decision.chosen_root, report.decision.chosen_step,
        *report.decision.fallback_roots, *report.decision.fallback_steps)]
    assert any("utility2_slot" in r for r in all_reprs), all_reprs
    assert repr(report.selected_goal).startswith("GrindCharacterXP"), (
        repr(report.selected_goal))
