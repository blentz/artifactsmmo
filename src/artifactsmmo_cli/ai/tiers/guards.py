"""Guard tier: state-pressure interrupts + prerequisite gates that preempt every
instrumental means. The only surviving priority ladder, scoped to guards.

Pure: predicates read state/game_data/history + an explicit SelectionContext
(player runtime flags). No Goal-class imports — the driver maps GuardKind to goals."""

from dataclasses import dataclass, field, replace
from enum import Enum

from artifactsmmo_cli.ai.bank_room import bank_has_room
from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.craft_relief import (
    CRAFT_RELIEF_FRACTION,
    craft_relief_candidates,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_caps import overstocked_items
from artifactsmmo_cli.ai.inventory_profile import inventory_profile
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.potion_supply import craft_potions_fires
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.thresholds import (
    CRITICAL_HP_FRACTION,
    DEPOSIT_FULL_FRACTION,
    PRESSURE_CRITICAL_FRACTION,
    PRESSURE_HIGH_FRACTION,
)
from artifactsmmo_cli.ai.world_state import WorldState

# CRITICAL_HP_FRACTION, DEPOSIT_FULL_FRACTION are imported from thresholds above.
# CRAFT_RELIEF_FRACTION (0.70) is re-imported from craft_relief.py (which now
# re-exports it from thresholds) so batch sizing and the guard share one value.
#
# DEPOSIT_FULL_FRACTION (0.90) is space-driven (spec 2026-06-07): deposit pressure
# only appears near-full so the player uses most of the bag. It is kept STRICTLY
# ABOVE DepositInventoryGoal._RAMP_START / PRESSURE_HIGH_FRACTION (0.85) so the
# DEPOSIT_FULL guard only fires where the deposit goal already has strictly-positive
# value — the proven liveness invariant `fires(DEPOSIT_FULL) ⇒ depositInventoryValue
# > 0` (Formal.Liveness.MeansFiring) requires DEPOSIT_FULL_FRACTION > PRESSURE_HIGH.
# The thresholds ladder enforces this ordering in one ascending block.
DISCARD_HIGH_FRACTION = PRESSURE_HIGH_FRACTION
DISCARD_CRITICAL_FRACTION = PRESSURE_CRITICAL_FRACTION
MAX_ACHIEVABLE_GAP = 5


@dataclass(frozen=True)
class SelectionContext:
    bank_accessible: bool
    bank_required_level: int
    bank_unlock_monster: str | None
    initial_xp: int
    task_exchange_min_coins: int
    combat_monster: str | None
    # Gold-reserve safety floor (`progression_reserve.reserve_floor(state,
    # game_data, None)`), computed by the player per cycle. Threaded here so
    # the BANK_EXPAND means guard applies the SAME reserve gate as the proven
    # should_expand_bank core WITHOUT means.py importing progression_reserve
    # (which imports back into the tiers package — circular). Default 0 =
    # reserve-free (legacy fixtures keep their old semantics).
    gold_reserve: int = 0
    # Long-term gear and tool codes — fed by player from the
    # CharacterObjective so the CRAFT_RELIEF guard can score gear/tool
    # craft candidates alongside the active task item. Empty fallback
    # leaves the guard task-only.
    target_gear: frozenset[str] = field(default_factory=frozenset)
    target_tools: frozenset[str] = field(default_factory=frozenset)
    # Usable-NOW gear/tool targets (near_term_gear ∪ target_tools): the codes the
    # skill-grind treats as `wanted` keepers so it crafts a real upgrade for skill
    # XP instead of a throwaway. Distinct from `target_gear` (endgame BiS, which is
    # never craftable at low char level — using it would make the preference dead).
    near_term_targets: frozenset[str] = field(default_factory=frozenset)
    # Post-level-up / post-fight-loss gear prioritization latch. Set by the
    # player's GearLatch and cleared when no craftable upgrade remains.
    gear_review_active: bool = False
    # Active-profile gear-demand KEEP map {code: keep_count} (spec
    # 2026-06-28-gear-loadout-profiles): the deduped per-code demand across the
    # active loadout profiles UNION the in-flight upgrade codes (+1 spare). This
    # is the GEAR portion of every keep/recycle/deposit/sell protection — it
    # REPLACES the `target_gear`/`target_tools` recipe-closure protection (which
    # remains the PURSUIT target for crafting). Empty (the default) means no
    # profile info → consumers fall back to the legacy blanket equippable keep,
    # so a freshly-started bot with no recorded profiles never strips its gear.
    gear_keep: dict[str, int] = field(default_factory=dict)


def protected_gear_codes(ctx: SelectionContext) -> frozenset[str]:
    """The set of gear codes the keep economy protects: the active-profile gear
    set UNION the in-flight upgrade codes (the keys of `ctx.gear_keep`). Empty
    when no profile info is available — callers then use their legacy fallback."""
    return frozenset(ctx.gear_keep)


def recycle_protected_codes(ctx: SelectionContext) -> frozenset[str]:
    """Recycle-eligibility protection: with profile info the per-code CAP
    (ctx.gear_keep, enforced inside `recyclable_surplus` via
    `useful_quantity_cap`) already keeps the demanded copies, so a blanket
    code exclusion on top turns "keep 1" into "keep all" — gear_keep
    ['copper_helmet']=1 hid a 41-helmet grind hoard from every recycle path
    (trace 2026-07-05). Blanket protection survives only for the profile-less
    legacy fallback, where no caps exist to do the job."""
    if ctx.gear_keep:
        return frozenset()
    return ctx.target_gear | ctx.target_tools


def _gear_protected(ctx: SelectionContext) -> frozenset[str]:
    """The GEAR codes the keep economy protects (recycle/sell/drain exclusion):
    the active-profile gear set ∪ in-flight upgrade (spec
    2026-06-28-gear-loadout-profiles) when profile info exists, else the legacy
    `target_gear | target_tools` fallback so a profile-less bot is unchanged."""
    if ctx.gear_keep:
        return protected_gear_codes(ctx)
    return ctx.target_gear | ctx.target_tools


class GuardKind(Enum):
    HP_CRITICAL = "hp_critical"
    REST_FOR_COMBAT = "rest_for_combat"  # combat target winnable at max_hp but not at current_hp
    BANK_UNLOCK = "bank_unlock"
    REACH_UNLOCK_LEVEL = "reach_unlock_level"
    DISCARD_CRITICAL = "discard_critical"
    CRAFT_RELIEF = "craft_relief"
    RECYCLE_RELIEF = "recycle_relief"
    SELL_RELIEF = "sell_relief"
    DEPOSIT_FULL = "deposit_full"
    DISCARD_HIGH = "discard_high"
    GEAR_REVIEW = "gear_review"  # post-level-up / post-loss gear prioritization
    CRAFT_POTIONS = "craft_potions"  # preemptively stock the utility-slot potion baseline


GUARD_ORDER: tuple[GuardKind, ...] = (
    GuardKind.HP_CRITICAL,
    GuardKind.REST_FOR_COMBAT,  # preempts the next Fight when current hp is insufficient
    GuardKind.BANK_UNLOCK,
    GuardKind.REACH_UNLOCK_LEVEL,
    GuardKind.DISCARD_CRITICAL,
    GuardKind.CRAFT_RELIEF,  # craft-before-deposit/discard when applicable
    GuardKind.RECYCLE_RELIEF,  # bank-full: recover materials before sell/discard
    GuardKind.SELL_RELIEF,  # bank-full: sell surplus to NPC before deposit/discard
    GuardKind.DEPOSIT_FULL,
    GuardKind.DISCARD_HIGH,
    GuardKind.GEAR_REVIEW,  # post-level-up / post-loss gear prioritization
    GuardKind.CRAFT_POTIONS,  # lowest-priority guard: stock potions before grind
)


def _has_sellable(state: WorldState, game_data: GameData) -> bool:
    """Item is sellable-NOW when it has a reachable buyer NPC (npc_location is not
    None) AND the server-side `tradeable` flag is true.

    Dormant event merchants appear in the price table but their location is None
    while their spawn window is closed — NpcSellAction.is_applicable rejects them
    on the same npc_location-is-None check.  Aligning the guard predicate with
    is_applicable prevents SELL_RELIEF from firing for unreachable buyers, which
    was causing a permanent bag-full livelock (no rung could act).

    Canonical definition — tiers/means.py imports this instead of duplicating it."""
    for code, qty in state.inventory.items():
        if qty <= 0:
            continue
        buyers = game_data.npcs_buying_item(code)
        if not buyers:
            continue
        stats = game_data.item_stats(code)
        if stats is not None and not stats.tradeable:
            continue
        # At least one buyer must be reachable now.
        if any(game_data.npc_location(npc) is not None for npc, _price in buyers):
            return True
    return False


def _quantity_fraction(state: WorldState) -> float:
    """QUANTITY pressure only (total items / quantity cap). Drives the DISCARD
    guards: deleting items is destructive and only warranted when the bag is
    genuinely drowning in accumulated junk QUANTITY — NOT merely because the slot
    cap is hit (that is relieved non-destructively by banking, below)."""
    if state.inventory_max <= 0:
        return 0.0
    return state.inventory_used / state.inventory_max


def _used_fraction(state: WorldState) -> float:
    """SPACE pressure = max of the quantity-fraction and the SLOT-fraction. The
    bag is "full" when EITHER the total-quantity cap OR the per-slot cap is hit,
    and in practice the 20 slots fill long before the ~124 quantity cap — live
    Robby 2026-07-10 sat at 20/20 SLOTS while only 76/124 QUANTITY (0.61), so a
    quantity-only metric never fired the space-relief guards (DEPOSIT_FULL,
    CRAFT_RELIEF) and doomed Craft(iron_bar) 497'd every cycle (recovery=None)
    with junk that served no plan for the next several levels. Feeding slot
    pressure here makes those guards bank/consolidate the junk and free a slot
    before the doomed action. NON-DESTRUCTIVE relief only — the DISCARD guards
    stay on `_quantity_fraction` so slot pressure never DELETES an item that
    banking would have saved (live regression caught 2026-07-11: DISCARD_CRITICAL
    deleting golden_egg ahead of DEPOSIT_FULL). Mirrors the slots-aware relief the
    slot-exhaustion fix wired into bank_selection / deposit_inventory (this
    guard-tier metric was the one spot left quantity-only)."""
    slot_fraction = (state.inventory_slots_used / state.inventory_slots_max
                     if state.inventory_slots_max > 0 else 0.0)
    return max(_quantity_fraction(state), slot_fraction)


def active_profile(state: WorldState, game_data: GameData,
                   ctx: SelectionContext,
                   step_profile: dict[str, int] | None = None) -> dict[str, int]:
    """The active goal's SOFT inventory profile, derived from the
    SelectionContext's long-term gear/tool codes + the committed
    crafting_target + active items-task (spec 2026-06-07). Deposit/discard
    never bank/delete a profile item below its target.

    `step_profile` is the resolved objective-step goal's needed map
    (item_code -> target_qty), merged at per-code max. Trace 2026-06-11 22:36
    (cycle 30): DISCARD_HIGH deleted a wooden_shield the active
    GatherMaterials grind goal was accumulating (held 2, needed 3) because the
    step goal's targets were invisible to this profile — it only covered
    crafting_target/gear/tools/task.

    Gear portion (spec 2026-06-28-gear-loadout-profiles): the recipe-closure
    roots and the finished-gear floor come from the ACTIVE-PROFILE gear set
    (`ctx.gear_keep`) when available, REPLACING the `target_gear`/`target_tools`
    closure. With no profile info (empty `gear_keep`) it falls back to the legacy
    `target_gear | target_tools` roots so a freshly-started bot is unchanged."""
    gear_codes: frozenset[str] = (protected_gear_codes(ctx) if ctx.gear_keep
                                  else ctx.target_gear | ctx.target_tools)
    profile = inventory_profile(state, game_data, gear_codes=gear_codes)
    # Active-profile finished gear (and the in-flight +1 spare) is protected at
    # its demand so deposit/discard never bank/delete it below that count.
    for code, keep in ctx.gear_keep.items():
        if keep > profile.get(code, 0):
            profile[code] = keep
    if step_profile:
        for code, qty in step_profile.items():
            if qty > profile.get(code, 0):
                profile[code] = qty
    return profile


def _fires(kind: GuardKind, state: WorldState, game_data: GameData,
           history: LearningStore | None, ctx: SelectionContext,
           step_profile: dict[str, int] | None = None) -> bool:
    if kind is GuardKind.HP_CRITICAL:
        return state.hp_percent < CRITICAL_HP_FRACTION
    if kind is GuardKind.REST_FOR_COMBAT:
        # Trace 2026-06-06 session 05:26: Robby kept firing FightAction at
        # hp=76 vs yellow_slime, losing each time because predict_win at
        # current_hp returned False while the picker's max_hp projection
        # said winnable. The cheap FightAction.is_applicable level filter
        # passed, so no Rest was inserted. This guard preempts the
        # Fight-at-low-HP path by forcing RestoreHP whenever:
        #   (a) a combat target is selected,
        #   (b) state.hp < state.max_hp (Rest is actionable),
        #   (c) predict_win at current hp is False, AND
        #   (d) predict_win at max_hp is True (i.e. resting MEANS we can
        #       then win — otherwise this isn't a hp problem, it's a gear
        #       problem and the picker should have rejected the target).
        if ctx.combat_monster is None:
            return False
        if state.hp >= state.max_hp:
            return False
        if predict_win(state, game_data, ctx.combat_monster):
            return False
        return predict_win(replace(state, hp=state.max_hp), game_data, ctx.combat_monster)
    if kind is GuardKind.BANK_UNLOCK:
        if ctx.bank_unlock_monster is None or ctx.bank_accessible:
            return False
        if state.xp > ctx.initial_xp:
            return False
        target_level = game_data.monster_level(ctx.bank_unlock_monster)
        # target_level == 0 means unknown; let the planner try and fail naturally.
        return target_level == 0 or state.level >= target_level - 1
    if kind is GuardKind.REACH_UNLOCK_LEVEL:
        return (ctx.bank_required_level > 0
                and state.level < ctx.bank_required_level
                and ctx.bank_required_level - state.level <= MAX_ACHIEVABLE_GAP)
    if kind is GuardKind.DISCARD_CRITICAL:
        # Overstock is genuine excess ABOVE the need/value inventory cap (the
        # active profile protects everything the goal still needs), so shedding it
        # is correct whether or not the bank has room — banking junk we will not
        # use for ~15 levels (e.g. 62 sap, target 1) just hoards it and, when the
        # bag is full, lets the deposit thrash on the active craft input instead
        # of clearing the junk (live Robby 2026-06-24: Withdraw(ash_plank)↔Deposit
        # loop, all "ok", no stuck signal). NOT gated on bank-full anymore.
        return (bool(overstocked_items(state, game_data,
                                       profile=active_profile(state, game_data, ctx,
                                                              step_profile)))
                and _quantity_fraction(state) >= DISCARD_CRITICAL_FRACTION)
    if kind is GuardKind.CRAFT_RELIEF:
        if _used_fraction(state) < CRAFT_RELIEF_FRACTION:
            return False
        return bool(craft_relief_candidates(
            state, game_data,
            step_items=frozenset(step_profile or ()),
        ))
    if kind is GuardKind.RECYCLE_RELIEF:
        # Gear protection (spec 2026-06-28-gear-loadout-profiles): the protected
        # set + the per-code cap come from the active-profile gear set when
        # available, else the legacy target_gear/target_tools fallback.
        recycle_protected = recycle_protected_codes(ctx)
        return (not bank_has_room(ctx.bank_accessible, state.bank_items,
                                  game_data.bank_capacity)
                and bool(recyclable_surplus(
                    state, game_data, recycle_protected,
                    gear_keep=ctx.gear_keep or None)))
    if kind is GuardKind.SELL_RELIEF:
        return (not bank_has_room(ctx.bank_accessible, state.bank_items,
                                  game_data.bank_capacity)
                and _has_sellable(state, game_data))
    if kind is GuardKind.DEPOSIT_FULL:
        return (ctx.bank_accessible
                and bank_has_room(ctx.bank_accessible, state.bank_items,
                                  game_data.bank_capacity)
                and _used_fraction(state) >= DEPOSIT_FULL_FRACTION
                and bool(select_bank_deposits(
                    state, game_data,
                    frozenset(active_profile(state, game_data, ctx, step_profile)))))
    if kind is GuardKind.DISCARD_HIGH:
        # Same as DISCARD_CRITICAL: overstock above the need/value cap is shed
        # regardless of bank room (don't hoard junk). Fires at the lower
        # DISCARD_HIGH watermark, BELOW DEPOSIT_FULL in priority — so a bag merely
        # high (not critical) deposits its retrievable buffer first, then sheds
        # the residual junk overstock.
        return (bool(overstocked_items(state, game_data,
                                       profile=active_profile(state, game_data, ctx,
                                                              step_profile)))
                and _quantity_fraction(state) >= DISCARD_HIGH_FRACTION)
    if kind is GuardKind.GEAR_REVIEW:
        return ctx.gear_review_active
    if kind is GuardKind.CRAFT_POTIONS:
        return craft_potions_fires(state, game_data)
    return False


def active_guards(state: WorldState, game_data: GameData,
                  history: LearningStore | None, ctx: SelectionContext,
                  step_profile: dict[str, int] | None = None) -> list[GuardKind]:
    """Triggered guards in ladder (preemption) order.

    history is accepted for signature parity with future learning-aware guards (currently unused).
    `step_profile` (the resolved step goal's needed map) joins the
    deposit/discard protection profile — see `active_profile`.
    """
    return [k for k in GUARD_ORDER
            if _fires(k, state, game_data, history, ctx, step_profile)]
