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
      unstocked (its EVENT_ONLY_CANDIDATES table narrowed instead — RE-
      NARROWED AGAIN by Task 2 below: the event's artifact-slot delta is
      gone entirely, see that constant's docstring). The FOLLOW-UP this fix
      surfaced —
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
      level (test_recipe_closure.py's secondary-drop tests).
  GAP-8 (band target outruns the fight window, l10_bag_pursuit — discovered
      2026-08-23 wiring the cascade to `band_combat_target`, task 5.2) —
      FIXED 2026-08-23 (task 5.2, fix round 1): a tier used to read "cleared"
      once every NORMAL monster in its band was winnable by stat prediction
      (`is_winnable`) alone, with no check that the monster was inside
      `FightAction`'s own `monster_level <= state.level +
      FIGHT_LEVEL_GAP_CEILING` structural window. At L10 here, tier 10
      (flying_snake L12, mushmush) read cleared by that definition, so
      `band_combat_target` advanced to tier 15's band and picked
      `highwayman` (L15) — stat-winnable with this loadout, but 15 > 10+2,
      so `FightAction` refused it outright: `GrindCharacterXP(highwayman)`
      planned to `plan_len: 0` in one node, and — because a non-None
      "winnable" path_monster outranks tier 3 in
      `GamePlayer._winnable_farm_target` — the windowed picker that would
      have found flying_snake never ran, so the arbiter fell all the way
      past combat to `MaintainConsumables`. `band_combat_target` now filters
      each band candidate on `FIGHT_LEVEL_GAP_CEILING` (imported from
      `ai.actions.combat`, the executor's own constant — not a second guess
      at the number) BEFORE the `is_winnable` check, so a candidate outside
      the executor's window is never offered at all and the tier is no
      longer considered "cleared" by it. At L10 this un-clears tier 10 (its
      OWN band member `flying_snake` is winnable and in-window, so tier 10
      is still cleared on its own account — the fix is in what tier 15
      offers, which is now nothing, i.e. `band_combat_target` returns
      `None`), so the cascade falls through to tier 3
      (`_pick_winnable_monster`), whose window `[9, 12]` finds
      `flying_snake` directly — restoring the ORIGINAL 2026-08-04
      derivation verbatim. Covered at the unit level
      (`test_band_target.py`'s ceiling tests) and the wiring level
      (`test_band_target_wiring.py`'s fall-through test); pinned again here
      at the scenario level, this time with no tripwire needed."""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import (
    SCENARIOS,
    ScenarioCharacter,
    load_bundle_game_data,
    scenario_state,
)
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, is_attainable_now
from artifactsmmo_cli.ai.tiers.progression_tree import objective_candidates
from artifactsmmo_cli.ai.tiers.pursuit_value import pursuit_value
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
    "artifact1_slot": "corrupted_skull",
    "artifact2_slot": "corrupted_skull",
    "artifact3_slot": "corrupted_skull",
}
"""What the corrupted_ogre event adds to l48_event_active's candidate
surface: the L20 ogre (winnable at this loadout) drops corrupted_gem, and
the permanent cultist_wizard sells crown + skull for it — with the event
down those monsters have no known spawn and the currency leaf is closed.

RE-DERIVED 2026-07-08 (Task-3 pursuit_value): the three artifact slots are
BACK in this table (corrupted_skull), reversing the equip_value-era Task-2
narrowing below. Under combat-dominant pursuit_value corrupted_skull
(combat_raw 8 -> pursuit_value 8000) strictly outranks perfect_pearl
(prospecting-only, combat_raw 0 -> pursuit_value 100) — exactly the class of
bug being fixed (a combat item must beat an all-efficiency item). So with the
event UP the artifact slots target corrupted_skull; with it DOWN they fall
back to perfect_pearl (the best NON-event artifact). The event's candidate
delta is therefore the helmet PLUS all three artifact slots.

HISTORICAL (equip_value era, now superseded by pursuit_value): under the flat
equip_value ruler perfect_pearl (value 201, all prospecting) outranked
corrupted_skull (value 17) so the artifact slots read perfect_pearl in BOTH
states and were dropped from this table (GAP-2 fix 2026-07-07 +
duplicate-slot-best-fill fix Task-2 2026-07-08). pursuit_value's combat
dominance flips that comparison, which is the intended correction."""


def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _state(name: str, gd: GameData) -> WorldState:
    return scenario_state(SCENARIOS[name], gd)


def _run(name: str) -> PlanReport:
    gd = load_bundle_game_data(BUNDLE)
    player = GamePlayer(character=name, history=None)
    player.seed_offline(_state(name, gd), gd)
    return player.plan_from_state()


def _bundle_with_tasks_farmer_completed() -> GameData:
    """The committed bundle with ONE bit flipped: the tasks_farmer achievement
    completed. Everything else is byte-identical, so any behaviour difference is
    attributable to that achievement and nothing else.

    tasks_trader stands on a tile conditional on it, and is the sole seller of
    jasper_crystal, so this is the difference between the satchel chain being
    shut and open."""
    raw = json.loads(BUNDLE.read_text())
    for ach in raw["achievements"]:
        if ach["code"] == "tasks_farmer":
            ach["completed_at"] = "2026-01-01T00:00:00+00:00"
            for objective in ach["objectives"]:
                objective["progress"] = objective["total"]
    return GameData.from_cache_bundle(raw)


def _run_with(name: str, gd: GameData) -> PlanReport:
    """`_run`, against a caller-supplied catalog."""
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


#: WAVE 3a: the `expect_no_work` flag this set fed is DELETED. It had already
#: been emptied on 2026-08-15 (the l35_boots_drop_farm entry turned out to be
#: a production bug in `xp_per_kill`'s zero band, not a fact about the
#: scenario), and wave 3a took the last user — `l48_band_adequate` — out of
#: the no-work category too: the resolution walk runs `actionable_step` on the
#: trunk, so it descends to a weapon prerequisite instead of handing
#: `objective_step_goal` a bare `ReachCharLevel` it answers None for. With no
#: no-work scenario left anywhere, the flag and this set are both gone. See
#: `search_bounds.assert_search_bounded`.


@pytest.mark.parametrize("name", NEW_SCENARIOS)
def test_slot_scenario_search_is_bounded(name: str) -> None:
    """Every tried goal bounded — the shared band-liveness bound."""
    assert_search_bounded(_run(name), name)


# --- Deliverable 1: event-gear pursuit across the L48 wall -----------------

def test_l48_event_candidates_are_event_gated() -> None:
    """The exact candidate delta the corrupted_ogre event buys, measured on
    the SAME state with only the game-data event overlay toggled (the very
    seeding seed_offline performs from state.active_events): with the event
    down the event items are absent (artifact slots fall back to
    perfect_pearl); with it up, corrupted_crown appears at helmet_slot AND
    corrupted_skull at all three artifact slots (RE-DERIVED 2026-07-08, Task-3
    pursuit_value: corrupted_skull's combat content now outranks the
    prospecting-only perfect_pearl — see EVENT_ONLY_CANDIDATES's docstring).
    This is the attribution test — the full-stack test below can't distinguish
    'event opened the leaf' from 'the leaf was open anyway' on its own."""
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
    """With the event up the planner must NOT Wait: an event-sourced candidate
    is on the gear sheet and the full stack plans the event-monster farm for its
    corrupted_gem currency — the attainability leaf the event opened. This is
    the wall-crossing behaviour l48_band_adequate proves impossible without
    events.

    WAVE 3a re-derived WHICH event candidate. `corrupted_crown` (helmet) is off
    the sheet: `gear_targets_with_blockers` gears for `gear_target_tier`, which
    is 30 here, and the crown sits above it — the helmet target is
    `obsidian_helmet`. The event's contribution is now `corrupted_skull` at all
    three artifact slots, and it is ATTAINABLE (`blocker is None`) precisely
    because the event opened its corrupted_gem route. The selected goal and the
    first action are UNCHANGED, which is the pursuit this test exists for.

    (An earlier fix-round draft of this docstring claimed `demon_horn` was
    `corrupted_crown`'s blocker. It is not — it blocks `gold_shield` and
    `conjurer_cloak`. The assertions below read the blocker map rather than
    restating it, so the claim and the code cannot drift again.)"""
    report = _run("l48_event_active")
    # Read the sheet off the SAME event-overlaid game data the run used
    # (`seed_offline` applies the overlay from `state.active_events`).
    gd_event = load_bundle_game_data(BUNDLE)
    overlay = GamePlayer(character="l48_event_active", history=None)
    overlay.seed_offline(_state("l48_event_active", gd_event), gd_event)
    assert overlay._objective is not None
    targets = overlay._objective.gear_targets_with_blockers(overlay.state, None)
    # THE EVENT'S OWN CONTRIBUTION, by name and by attainability — not "any
    # corrupted-anything root", which the previous form degenerated to.
    for slot in ("artifact1_slot", "artifact2_slot", "artifact3_slot"):
        assert targets[slot].code == "corrupted_skull", (slot, targets[slot])
        assert targets[slot].blocker is None, (slot, targets[slot])
    assert any(r.root_repr == "ObtainItem(code='corrupted_skull', quantity=1, "
               "slot='artifact1_slot')" for r in report.decision.ranking), \
        report.decision.ranking
    assert repr(report.selected_goal) != "Wait", (
        repr(report.selected_goal), report.plan)
    assert repr(report.selected_goal).startswith(
        "GatherMaterials(corrupted_gem"), repr(report.selected_goal)
    assert report.plan and repr(report.plan[0]).startswith(
        "Fight(corrupted_ogre"), report.plan


def test_l48_no_event_witness_pursues_no_event_gear() -> None:
    """Isolation: the l48_band_adequate witness (zero-stat, no events) must
    keep pinning the wall — no event gear is pursued there. If this ever flips,
    the event-pursuit result above is no longer attributable to the event
    seam and both scenarios must be re-derived.

    WAVE 3a: the witness no longer WAITS. Two changes compose. The walk names
    the wall as `chosen_root is None` instead of handing back an unreachable
    `ReachCharLevel(50)`; and the trunk fallback now goes through
    `actionable_step`, so it descends to its weapon prerequisite and the
    arbiter reaches a mithril_bar craft chain instead of idling. Neither is
    event gear, so the isolation this test provides is unaffected — but the
    assertion is now about WHAT is pursued rather than about Wait, because
    Wait was only ever a proxy for "nothing event-shaped happened here".

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
    assert repr(report.selected_goal) == "GatherMaterials(mithril_bar, {mithril_bar:11})", (
        repr(report.selected_goal), report.plan)
    assert report.decision.chosen_root is None
    assert not any("corrupted" in r.root_repr for r in report.decision.ranking), \
        report.decision.ranking


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
    # satchel does NOT propagate upward — and the docstring's parenthetical above
    # is why: it assumed jasper_crystal was "independently task-earnable, the C4
    # funding loop always available". It is bought with tasks_coin from
    # tasks_trader, who stands on a tile conditional on the tasks_farmer
    # achievement (0/100 on the real account, now pinned in the bundle). The
    # trader is unroutable, so the third material is unobtainable.
    #
    # The two asserts below are what keep this a GAP-1 test rather than a
    # jasper_crystal test: the banked-stock credit still answers YES for both
    # materials it is about, and the ONLY thing missing upward is the third.
    assert not is_attainable_now("satchel", state, gd)
    assert not is_attainable_now("jasper_crystal", state, gd)
    assert gd.npc_location("tasks_trader") is None


def test_l10_bag_pursuit_satchel_gated_and_iron_is_the_fixed_point() -> None:
    """Task 5.2 fix round 1 (2026-08-23, GAP-8 in the module docstring)
    round-tripped the closing combat assertions: wiring the cascade to
    `band_combat_target` briefly broke them (tier 15's band offered a
    stat-winnable but unfightable `highwayman`, so the arbiter fell all the
    way to `MaintainConsumables`), and adding the executor's
    `FIGHT_LEVEL_GAP_CEILING` to the band filter restored this derivation
    verbatim — `band_combat_target` now returns `None` for tier 15 (nothing
    in its band is both winnable AND in-window), so the cascade falls
    through to tier 3's windowed picker, which finds `flying_snake` exactly
    as it did before task 5.2 touched anything. See GAP-8 for the full
    mechanism.

    RE-DERIVED AGAIN 2026-08-04 (pursuit_value unification).

    The previous derivation had `iron_armor` beating `adventurer_vest` on the
    flat `combat_raw` sum (70000 to 66020) while the RULER said the opposite
    (equip_value 174_400 to 142_000) — the acquisition path and the picker
    holding different opinions about one slot, which is the whole defect class
    this epic removes. `pursuit_value`'s combat term is the ruler's own now, so
    the vest wins on both and the scenario's loadout was re-converged to it
    (see scenario.py's RE-FIXED-POINT note). With every slot at the ruler's own
    fixed point, near_term_gear is EMPTY and the tree falls through to the
    char-level trunk, grinding the same winnable cow directly.

    satchel needs jasper_crystal, bought with tasks_coin from tasks_trader, who
    stands on a tile conditional on the tasks_farmer achievement — 0/100 on the
    real account, now pinned in the bundle. The trader is unroutable, so the
    satchel chain is SHUT and bag_slot is not a near_term_gear candidate at all,
    not even a fallback root (region soundness, 2026-07-26).

    Prior derivation (2026-07-07 hp-derivation fix wave): the original pin
    ('satchel invisible at L10') was CONTAMINATED — it relied on the
    harness's hand-declared max_hp (240) undershooting the server's real
    115 + 5*level + gear formula (375 at this loadout), which made cow read
    unwinnable. At the real 375 hp cow IS winnable, which is why the trunk
    grind below has a live fight to plan."""
    gd = _bundle()
    state = _state("l10_bag_pursuit", gd)
    objective = CharacterObjective.from_game_data(gd)
    assert (state.bank_items or {}).get("cowhide", 0) >= 5  # mats really banked
    assert is_winnable(state, gd, "cow")
    # The satchel chain is shut at its THIRD material, not at cow/cowhide: the
    # monster-drop leaf this scenario is built on is still winnable above.
    assert not is_attainable_now("satchel", state, gd)
    assert gd.npc_location("tasks_trader") is None
    assert objective.near_term_gear(state) == {}
    # The attribution: the equipped vest is not merely unranked, it is the
    # RULER's own argmax for the slot — and the acquisition ruler agrees, which
    # is the property that stops the two authorities fighting over it.
    assert pursuit_value(gd.item_stats("adventurer_vest")) \
        > pursuit_value(gd.item_stats("iron_armor"))
    assert equip_value(gd.item_stats("adventurer_vest")) \
        > equip_value(gd.item_stats("iron_armor"))

    report = _run("l10_bag_pursuit")
    # WAVE 3a: the chosen root is the furthest-behind slot on the TIER sheet
    # (three empty artifact slots), not the trunk — `near_term_gear` being
    # empty no longer means the gear sheet is. The satchel claim, which is what
    # this test is named for, is unaffected and asserted below; the trunk is
    # still offered, so the grind this scenario pins remains reachable and is
    # in fact what the arbiter selects.
    assert report.decision.chosen_root == ObtainItem(
        code="novice_guide", quantity=1, slot="artifact1_slot")
    assert ReachCharLevel(level=20) in report.decision.fallback_roots
    assert not any(r.code == "satchel" for r in report.decision.fallback_roots
                   if isinstance(r, ObtainItem)), report.decision.fallback_roots
    # The grind target moved with the re-converged loadout (2026-08-04): at the
    # ruler's own fixed point this L10 build beats `flying_snake`, which out-XPs
    # the cow it used to grind. Still a plain combat grind on the trunk, which
    # is what this pin is about. GAP-8 (fix round 1, 2026-08-23) briefly moved
    # this to MaintainConsumables via an unfightable band pick (highwayman,
    # tier 15) — see the module docstring for the mechanism; with
    # FIGHT_LEVEL_GAP_CEILING now filtering the band, tier 15 offers nothing
    # and the cascade falls through to tier 3, which finds flying_snake again.
    # WAVE 3a: the artifact/bag roots ahead of the grind are new — they are the
    # tier sheet's empty slots, walked in order before the trunk is reached.
    # None of them plans, so the grind still wins; the list is spelled out
    # rather than trimmed so a future change that makes one of them plannable
    # (and silently displaces the grind) fails here.
    assert [g["goal"] for g in report.goals_tried] == [
        "UpgradeEquipment(novice_guide->artifact1_slot)",
        "UpgradeEquipment(novice_guide->artifact2_slot)",
        "UpgradeEquipment(novice_guide->artifact3_slot)",
        "GatherMaterials(backpack, {backpack:1})",
        "GrindCharacterXP(flying_snake)",
    ], report.goals_tried
    assert repr(report.selected_goal).startswith("GrindCharacterXP(flying_snake"), (
        repr(report.selected_goal))
    assert report.plan and repr(report.plan[0]).startswith("Fight(flying_snake"), \
        report.plan


def test_l12_bag_pursuit_satchel_chain_gated() -> None:
    """RE-DERIVED (region soundness): the isolation witness that the satchel chain itself works: +2 levels
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
    # Gate SHUT on the real account: the isolation leaves nothing behind, because
    # the sole candidate this scenario isolates is itself unreachable.
    assert objective.near_term_gear(state) == {}
    assert not is_attainable_now("satchel", state, gd)
    assert gd.npc_location("tasks_trader") is None


def test_l12_bag_pursuit_satchel_becomes_attainable_but_is_no_longer_pursued() -> None:
    """RENAMED IN WAVE 3a fix-round 1. LOST: the decision half. The achievement
    still opens satchel at the OBJECTIVE layer (asserted below, unchanged), but
    the walk targets `backpack` and the C4 funding route is never planned.
    Wave 4 restores it (task-6 report, R4).

    The other half, and the one that kept the C4 funding chain covered.

    Same bundle, ONE bit flipped — tasks_farmer completed — and every assertion
    the shut-gate twin above used to make comes back verbatim: bag_slot ->
    satchel as the sole candidate, jasper_crystal as the step, and the full
    ReachCurrency(tasks_coin) -> AcceptTask funding route.

    This is what makes the suppression a GATE and not a regression. Without it,
    "satchel is unreachable" would be indistinguishable from the planner having
    lost the ability to pursue a bag at all, and the C4 pipeline would sit
    uncovered until someone completed 100 tasks."""
    gd = _bundle_with_tasks_farmer_completed()
    state = _state("l12_bag_pursuit", gd)
    objective = CharacterObjective.from_game_data(gd)
    assert gd.achievement_completed("tasks_farmer")
    assert gd.npc_location("tasks_trader") == (5, 11)
    assert objective.near_term_gear(state) == {"bag_slot": "satchel"}
    assert is_attainable_now("satchel", state, gd)

    report = _run_with("l12_bag_pursuit", gd)
    # WAVE 3a LOST THE DECISION HALF OF THIS TEST, and the loss is pinned here
    # rather than trimmed away. The walk reads `gear_targets_with_blockers`,
    # which picks the best bag AT `gear_target_tier` — the rung being CLEARED,
    # CAPPED by character level. MEASURED here: `next_uncleared_tier` is 15 and
    # the level cap is 10, so `gear_target_tier` is **10** — NOT 1. (A first
    # draft of this comment blamed a "rung-1 collapse"; that story was withdrawn
    # in fix-round 1 and this is one of the artifacts it had not reached.) At
    # rung 10 the best bag is `backpack`, not `satchel`, so the whole
    # ReachCurrency(tasks_coin) -> AcceptTask funding route this test was
    # written to cover goes untried. The cap is ordinary, so this is NOT a
    # fixture artefact: it bites live for any character that has not cleared
    # its level's band.
    #
    # The OBJECTIVE-level half above is untouched and still bites: with the
    # achievement landed, `near_term_gear` names satchel and
    # `is_attainable_now` agrees; the shut-gate twin asserts both go away. So
    # the gate is still a gate. What is no longer covered anywhere is the C4
    # pipeline running end to end, which is written up in
    # `.superpowers/sdd/PLAN_wave3a_cutover/task-6-report.md`.
    assert not any(isinstance(r, ObtainItem) and r.code == "satchel"
                   for r in report.decision.fallback_roots), \
        report.decision.fallback_roots
    assert ObtainItem(code="backpack", quantity=1, slot="bag_slot") in \
        report.decision.fallback_roots, report.decision.fallback_roots


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


def test_l35_artifact_fill_pearl_route_is_off_the_sheet_and_unplanned() -> None:
    """RENAMED IN WAVE 3a fix-round 1. LOST: `perfect_pearl` is off the gear
    sheet, the small_pearls route is neither the root nor tried, and the
    scenario ends in `Wait`. GAP-2's `_gatherable` fix keeps its own direct
    test (`test_l35_artifact_small_pearls_gatherable_via_full_drop_set`); wave 4
    owns restoring the end-to-end route — task-6 report, R4.

    GAP-7 FIXED (2026-07-08) — the former tripwire
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
    # RE-FIXED-POINT 2026-07-08 (Task-3 pursuit_value): weapon_slot/boots_slot
    # are now equipped at their combat argmax (wooden_club/snakeskin_boots), so
    # the artifact slots are the SOLE candidates and perfect_pearl is the chosen
    # root outright — no old_boots demotion chain any more (old_boots is
    # correctly outranked by snakeskin_boots and no longer a candidate; its
    # drop-farm coverage moved to l35_boots_drop_farm's wooden_club re-target).
    # WAVE 3a: `perfect_pearl` is off the sheet entirely and the artifact-slot
    # target is `novice_guide`. `gear_targets_with_blockers` gears for
    # `gear_target_tier` — the rung being CLEARED, capped by character level.
    # MEASURED here: `next_uncleared_tier` is 20 against a level-35 character,
    # so the tier is **20** — NOT 1, and `perfect_pearl` sits above it. (A first
    # draft blamed a "rung-1 collapse"; withdrawn in fix-round 1, and this is
    # one of the artifacts it had not reached.) An ordinary cap, so this is not
    # a fixture artefact. GAP-2's fix is NOT reverted: the `objective._gatherable` half is
    # pinned directly by
    # `test_l35_artifact_small_pearls_gatherable_via_full_drop_set`. What is no
    # longer covered is the small_pearls ROUTE being planned end to end, which
    # is written up in the task-6 report.
    report = _run("l35_artifact_fill")
    assert report.decision.chosen_root == ObtainItem(
        code="novice_guide", quantity=1, slot="artifact1_slot")
    assert not any("perfect_pearl" in r.root_repr for r in report.decision.ranking), \
        report.decision.ranking
    # The pinned outcome, WAVE 3a. With perfect_pearl off the sheet the
    # small_pearls gather is never tried and no candidate on the sheet plans,
    # so the arbiter reaches its documented last resort. The BATCHED /
    # CLOSURE-SIZED node-count pins that stood here measured
    # `GatherMaterials(small_pearls)`, a goal this scenario no longer produces;
    # they are not restated against a different goal, because that would be
    # re-pointing a measurement at something it never measured. The batch
    # mechanism keeps its own coverage in test_currency_grind.
    assert repr(report.selected_goal) == "Wait", (
        repr(report.selected_goal), report.plan)
    assert not any("small_pearls" in str(g.get("goal", ""))
                   for g in report.goals_tried), report.goals_tried


def test_l35_boots_drop_farm_fights_grey_dropper() -> None:
    """GAP-6 coverage keeper — UpgradeEquipmentGoal drop-farms a recipe-less,
    non-purchasable, pure monster-drop equip target via its grey winnable dropper.

    RE-TARGETED 2026-07-15 (winnability guard): the prior version asserted the
    ARBITER picks wooden_club as chosen_root. The predict_win weapon-winnability
    guard now correctly SUPPRESSES wooden_club at the targeting layer — at L35
    fully-geared its marginal winnability is 0 (owning it unlocks no monster the
    character cannot already beat), so grinding/farming toward it is a combat
    no-op and the arbiter rightly falls to ReachCharLevel. That guard is a
    TARGETING decision; it is orthogonal to the drop-farm EMISSION mechanism this
    test covers, which still fires for any pure-drop target that IS pursued.
    We cover the mechanism directly: with the goal pinned to the pure-drop
    wooden_club, UpgradeEquipmentGoal.relevant_actions emits its sole winnable
    dropper — ogre (L20, grey at L35, xp_per_kill == 0, 15 levels down) — as the
    drop_farm Fight (proven xp-gate bypass) plus the synthesized
    Equip(wooden_club->weapon_slot) leg, and the goal PLANS Fight(ogre) -> Equip.
    A healthy character never idles on a farmable upgrade it is actually pursuing.

    LIMITATION (honest-outcome rule): no scenario in THIS bundle can drive a
    guard-surviving pure-drop to chosen_root at the ARBITER level — every grey
    weapon drop is marginal-0 (it is low-tier, and a character >=15 levels above
    its dropper already out-damages it), and every non-weapon pure-drop is
    outranked by an attainable-now craftable in its slot (verified: emptying any
    non-weapon slot on this state makes near_term_gear pick a craftable, never a
    drop). So the full arbiter path for a pure-drop root is no longer exercisable
    here; this mechanism-level pin is the honest maximum. Fixing the bundle to
    host a guard-surviving non-weapon pure-drop argmax should restore an
    arbiter-level assertion and may fail this pin."""
    gd = load_bundle_game_data(BUNDLE)
    state = _state("l35_boots_drop_farm", gd)
    player = GamePlayer(character="l35_boots_drop_farm", history=None)
    player.seed_offline(state, gd)
    actions = player._build_actions()
    goal = UpgradeEquipmentGoal(committed_target=("wooden_club", "weapon_slot"))
    relevant = goal.relevant_actions(actions, state, gd)
    fights = [a for a in relevant if repr(a) == "Fight(ogre)"]
    assert fights and all(a.drop_farm for a in fights), relevant
    assert any(repr(a) == "Equip(wooden_club->weapon_slot)" for a in relevant), \
        relevant
    plan = player.planner.plan(state, goal, actions, gd, budget_seconds=10.0)
    assert [repr(a) for a in plan] == \
        ["Fight(ogre)", "Equip(wooden_club->weapon_slot)"], plan


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

def test_l20_dual_utility_empty_utility_slots_are_not_decision_candidates() -> None:
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
    utility provisioning is ever promoted, this pin flips.

    WAVE 3a FLIPPED IT THE OTHER WAY, and this is a real loss, recorded here
    rather than quietly re-pinned. Utility potions were `_utility_candidates`,
    part of the deleted candidate pass. The resolution walk reads
    `gear_targets_with_blockers`, which is EQUIPMENT slots only, so a potion
    can no longer be a root or a fallback root at all — not first, not last.
    Potion provisioning survives only through the arbiter's own guard rungs
    (`MaintainConsumables` / the combat-justified CRAFT_POTIONS rung,
    project_potion_combat_justification), which this file does not cover.

    The verdict this test was named for (XP outranks an empty utility slot) is
    therefore no longer expressible: there is nothing to outrank. What IS
    asserted is the fact that replaced it, so the absence is a pinned claim and
    not a silently shorter list."""
    report = _run("l20_dual_utility")
    assert report.decision.chosen_root == ReachSkillLevel(
        skill="gearcrafting", level=16)
    assert not any("utility" in repr(r) for r in report.decision.fallback_roots), \
        report.decision.fallback_roots
    assert ReachCharLevel(level=30) in report.decision.fallback_roots


def test_l20_one_stocked_utility2_is_a_candidate_but_not_a_decision_root() -> None:
    """RENAMED IN WAVE 3a fix-round 1. LOST: utility potions are not equipment
    slots, so no potion reaches `fallback_roots` at all — the GAP-5 claim now
    lives only at the `objective_candidates` layer, where it is asserted below.
    Wave 4 owns the restoration (task-6 report, R3).

    GAP-5 FIXED 2026-07-07 (renamed from ..._never_targeted, whose
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
    the argmax in this scenario).

    WAVE 3a: the GAP-5 claim now lives entirely at the
    `utility_potion_targets` / `objective_candidates` layer, which is where it
    was always measured — the two `objective.*` assertions below are unchanged
    and still bite. What is gone is the DECISION-level half: utility potions
    are not equipment slots, so `gear_targets_with_blockers` never sees them
    and no potion appears in `fallback_roots`. See
    `test_l20_dual_utility_empty_utility_slots_are_not_decision_candidates`
    for the full account of that loss."""
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

    # The GAP-5 fix itself, measured where it lives: the PER-SLOT stock check
    # keeps utility1 (stocked) out and lets utility2 (empty) through. This half
    # is untouched by wave 3a.
    candidates = objective_candidates(state, gd, objective)
    assert [c.slot for c in candidates if c.slot.startswith("utility")] == \
        ["utility2_slot"], candidates

    report = _run("l20_dual_utility_one_stocked")
    assert report.decision.chosen_root == ReachSkillLevel(
        skill="gearcrafting", level=16)
    assert not any("utility" in repr(r) for r in report.decision.fallback_roots), \
        report.decision.fallback_roots
