"""`SelectionContext` — the per-cycle player runtime flags the pure selection
cores read (guards, keep authority, deposit selection).

It lives in its OWN module, below every consumer, because the keep authority
(`ai/inventory_keep.py`) and the deposit selector (`ai/bank_selection.py`) both
need it while `ai/tiers/guards.py` — its historical home — imports THEM. Keeping
the dataclass in `guards` made `guards -> bank_selection -> inventory_keep ->
guards` a cycle the moment deposit started asking the keep authority how many
copies it may bank. `tiers.guards` re-exports the name, so every existing
`from artifactsmmo_cli.ai.tiers.guards import SelectionContext` still resolves.

Pure data: no behavior, so this module imports nothing else from the package —
the exceptions are `TurnIn` below, a leaf pure-data class (`ai.currency_turnin`
imports only stdlib), `ChosenLoadout` (`ai.chosen_loadout`, pure data over
`thresholds`), `PartyLease` (`ai.party_lease_core`, pure data over
`world_state`), `GearObjective` (`ai.gear_objective_result`, pure data over
`gear_objective_core`) and `LearnedDrops` (`ai.learned_drops`, pure data over
`drop_chance_core`), none of which carries a cycle risk of its own.
"""

from dataclasses import dataclass, field
from fractions import Fraction

from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout
from artifactsmmo_cli.ai.currency_turnin import TurnIn
from artifactsmmo_cli.ai.fight_seconds_core import FightSecondsModel
from artifactsmmo_cli.ai.fleet_piece import FleetPiece
from artifactsmmo_cli.ai.gear_objective_result import GearObjective
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.party_lease_core import PartyLease


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
    # 2026-08-19 (S-051 + the USER's no-immediate-redraw rule). True when a task
    # DRAW is owed for the course in flight. The task objective takes a draw only
    # when it is set (`task_accept.accept_due`; the ACCEPT_TASK rung until Phase
    # 5-2c-iii-c-2 #3), and taking the draw clears it. Without the gate, accept
    # and discard would spin at a coin a cycle — see
    # docs/PLAN_task_draw_and_judge.md.
    #
    # Defaults False so a caller that does not manage it gets no draw.
    draw_owed: bool = False
    # The master to draw at when a draw is owed (`task_worth.pool_draw`: the due
    # master with the higher worthy share). None = let `choose_taskmaster` pick.
    draw_master: str | None = None
    # Account gold (pocket + bank) is below the larger of the progression
    # reserve and the gold the previous cycle's chosen root will spend at
    # vendors (set by the player, `GamePlayer._gold_short`). A task's GOLD
    # reason needs it (`task_worth`; USER 2026-10-07: "Both, the larger").
    # False for a caller that does not compute it.
    gold_short: bool = False
    # The XP the goal-action DAG still demands (`xp_demand`, set by the
    # player): skills above their current level, and whether character level
    # is demanded. A task's XP is a reason only for demanded XP (USER
    # 2026-10-07: the seesaw is emergent, never a phase rule).
    skill_demand: frozenset[str] = frozenset()
    # The role this character holds and every role a live character holds
    # (`CoordinationStore.live_leases`), set by the player each cycle. None /
    # empty on a single-character run. `food_producer.may_make_food` reads
    # them: only the owner of a food's craft makes it (spec 2026-10-13 §4).
    role: str | None = None
    fleet_roles: frozenset[str] = frozenset()
    level_demanded: bool = False
    # The fleet consumable floor's shortfall: (consumable, fleet deficit) per
    # class below its floor (`consumable_floor.supply_shortfall`, set by the
    # player). A food is published only when it is worth making (the chosen
    # loadout's `made_food`, spec 2026-10-13 §4). Read by the orphan-skill gate
    # (`decisions.root._orphan_skill_roots`), which reads a FOOD row only for
    # the food's producer (`food_producer.may_make_food`), and by
    # `task_worth.short_items`. NOT a `xp_demand.demand_roots` seed (spec §2:
    # the shortfall must not make its own skills useful XP).
    supply_shortfall: tuple[tuple[str, int], ...] = ()
    # (monster, fights, wins) at the character's level in that fight's loadout,
    # for every monster it has lost to (`combat.fight_records`, set by the
    # player). A fight's price carries its learned loss rate
    # (`loss_risk_core`; USER 2026-10-08, "Price the loss risk"). Empty for a
    # caller without history: the prediction alone prices the fight.
    fight_records: tuple[tuple[str, int, int], ...] = ()
    # The item this character's live supply claim is producing and its recipe
    # closure (set by the player). Reserved from healing: RestoreHP may neither
    # cook nor eat them (USER 2026-10-08: "Reserve the claimed batch"; live,
    # R2D2 ate the cooked_rat_meat its SupplyBank claim made, 4 of 4).
    supply_reserved: frozenset[str] = frozenset()
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
    # Active-profile gear-demand KEEP map {code: keep_count} (spec
    # 2026-06-28-gear-loadout-profiles): the deduped per-code demand across the
    # active loadout profiles UNION the in-flight upgrade codes (+1 spare). This
    # is the GEAR portion of every keep/recycle/deposit/sell protection — it
    # REPLACES the `target_gear`/`target_tools` recipe-closure protection (which
    # remains the PURSUIT target for crafting). Empty (the default) means no
    # profile info → consumers fall back to the legacy blanket equippable keep,
    # so a freshly-started bot with no recorded profiles never strips its gear.
    gear_keep: dict[str, int] = field(default_factory=dict)
    # Active objective-step goal's material profile {code: needed_qty} — the
    # GOAL_MATERIALS keep reason (`ai/inventory_keep.py`) reads it so the
    # materials the current step is accumulating are never banked out from
    # under it. Empty (the default) means "no active step profile";
    # `StrategyArbiter.select` binds it per cycle from the SAME
    # `_step_protection_profile` map it hands the deposit/discard guards (the
    # step goal is resolved FROM this ctx, so it cannot be filled in earlier).
    # A DEFAULT is mandatory: ~26 formal/diff helpers
    # construct SelectionContext positionally-by-keyword and a required field
    # would break every one of them.
    step_profile: dict[str, int] = field(default_factory=dict)
    # (item_code, quantity, demand) this character should produce for a
    # sibling this cycle, or None when nothing is servable. Populated by the
    # player's per-cycle coordination block; None on every single-character
    # run (Task 11 wires the producer — this means is inert until then).
    supply_target: tuple[str, int, int] | None = None
    # {item_code: quantity} of BANK stock a SIBLING has already committed to
    # withdrawing this cycle — `CoordinationStore.sibling_bank_claims`, read
    # once per cycle by the player's coordination block and threaded here as
    # DATA, the same seam as `supply_target`. Empty (the
    # default) on every single-character run and whenever no coordination
    # store is attached, which makes `bank_drain.bank_drain_excess`
    # byte-identical to its pre-coordination behaviour.
    #
    # The bank is ACCOUNT-shared, so all five `play --all` children hold the
    # same `bank_items` and derive the same shed licence from it; the losers
    # of that race pay HTTP 478 "Missing required item(s)" out of the per-IP
    # request budget (7 of 72 cycles, 2026-08-05 validation run). Subtracting
    # this from the bank's AVAILABLE quantity is what stops four characters
    # planning the same withdraw.
    #
    # AVAILABILITY, NOT OWNERSHIP: it never reaches `destroyable`. A sibling's
    # claim does not change what the ACCOUNT owns (the bank is shared, so the
    # keep authority's ownership cap is account-wide and unaffected) — it
    # changes only how many copies are still there to take.
    sibling_bank_claims: dict[str, int] = field(default_factory=dict)
    # Grand Exchange order ids a SIBLING has already committed to cancelling —
    # `CoordinationStore.sibling_order_claims`, read once per cycle by the
    # player's coordination block and threaded here as DATA, the same seam as
    # `sibling_bank_claims` directly above. Empty (the default) on every
    # single-character run and whenever no coordination store is attached,
    # which makes `cancel_selection.cancel_targets` byte-identical to its
    # pre-coordination behaviour.
    #
    # GE orders are ACCOUNT-scoped: `/my/grandexchange/orders` returns the same
    # list to all five children, so each ages the same order past TTL_CYCLES and
    # each plans the same cancel. The losers pay HTTP 404 "Order not found" out
    # of the per-IP request budget (6 of 20 distinct ids contested, 8 wasted
    # requests, 2026-08-10 five-character run).
    #
    # A SET, not a mapping: the only question asked of it is membership. There
    # is no quantity to net out — a cancel either happens or it does not.
    sibling_order_claims: frozenset[str] = field(default_factory=frozenset)
    # This cycle's resolved fleet dual-role-currency purchase, or None —
    # `CoordinationStore.publish_holdings`/`sibling_holdings` (Task 2) let
    # every character see the SAME fleet total cross a vendor's price on the
    # SAME cycle, `GamePlayer._resolve_turn_in` (Task 5) is what decides
    # whether that crossing is real for THIS character (its own loadout and
    # level, `ai.currency_turnin`'s pure rules) and which one character wins
    # the exclusive `claim_turn_in` election. Set on every character that
    # independently qualifies as a candidate buyer — the winner (`buyer ==
    # self.character`) and any loser (`buyer` names the incumbent) alike;
    # None for a character with no qualifying candidate of its own, which is
    # every single-character run and every cycle nothing is affordable.
    turn_in: TurnIn | None = None
    # (currency_code, units this character should surrender to the turn-in
    # buyer) this cycle, or None. Populated on any NON-buyer that HOLDS units
    # of the currency, by either of `GamePlayer._resolve_turn_in`'s two
    # routes: a character that itself qualified as a candidate buyer and lost
    # the `claim_turn_in` election, OR — the case that makes the feature work
    # on the live fleet at all — a character BELOW the item's level that can
    # never be a buyer and stands down to a sibling's live claim
    # (`_adopt_sibling_claim`). Never on the buyer (nothing to surrender to
    # itself), never when `turn_in` is None, and never when the holding is
    # zero — so `recall is None` does NOT mean "I am the buyer", and goal
    # selection keys on `turn_in.buyer == state.character` instead
    # (strategy_driver.map_means; a second buyer double-spends the fleet's
    # currency). Same per-cycle lifecycle as `turn_in`.
    recall: tuple[str, int] | None = None
    # {item_code} some SIBLING wants but marked NOT self-servable for itself —
    # `CoordinationStore.sibling_demand_asymmetric`, read once per cycle by the
    # player's coordination block and threaded here as DATA, the same seam as
    # `supply_target`. Empty (the default) on every
    # single-character run and whenever no coordination store is attached.
    #
    # This is the signal that distinguishes "a sibling asked but could gather
    # it itself" (not worth pausing for) from "nobody nearby can make this"
    # (the request the SUPPLY rung exists to serve) — see
    # `MaterialDemand.self_servable`'s docstring for why the requester's own
    # ability, not just the quantity, has to ride on the row.
    asymmetric_demand: frozenset[str] = field(default_factory=frozenset)

    # Best crafting-skill level held by any LIVE SIBLING, per skill —
    # `CoordinationStore.sibling_skill_levels`, read once per cycle by the player
    # and threaded here as DATA, the same seam as `supply_target`,
    # `sibling_bank_claims` and `asymmetric_demand`. Empty (the default) on every
    # single-character run, which makes the sibling route silently absent rather
    # than wrong.
    #
    # CAPABILITY, NOT AVAILABILITY: it says a sibling COULD craft this today, not
    # that any units exist. `acquisition_cost._sibling_craft_option` still charges
    # the recipe as inputs and the measured request cost as the unlock, so a
    # sibling saves the SKILL GATE and nothing else.
    sibling_skills: dict[str, int] = field(default_factory=dict)
    # The siblings' dual-role units, WORN PLUS CARRIED, per code
    # (`CoordinationStore.sibling_holdings`, the ledger the turn-in election
    # counts): a currency the fleet pools is short only by what the WHOLE fleet
    # lacks (`obtain_item_routing._equippable_goal`). Live 2026-10-13: four
    # characters each bought medals toward their OWN lich_race_trophy shortfall,
    # emptied the bank of event_ticket between them, then gathered tickets
    # while the fleet already held the 10 medals. Empty without a store.
    sibling_holdings: dict[str, int] = field(default_factory=dict)
    # The fleet's shared skill climb (spec 2026-10-18 §2.5), read once per
    # cycle by the player's coordination block and threaded here as DATA, the
    # same seam as `sibling_skills`. All empty on a single-character run and
    # on every caller with no coordination store, which leaves the amortized
    # sibling climb (`acquisition_cost._sibling_craft_option`) and the
    # crafter's fleet pieces (`fleet_pieces`) absent rather than wrong.
    #
    # `sibling_skill_ledger`: each live sibling's published skill levels
    # (`CoordinationStore.sibling_skill_ledger`), per character — the climber
    # is chosen per character, which `sibling_skills`' fleet max cannot do.
    sibling_skill_ledger: dict[str, dict[str, int]] = field(default_factory=dict)
    # craft skill -> its assigned climber (`fleet_climber.fleet_climbers`,
    # ruling T7a), kept only where that climber can serve the skill: it holds,
    # or is free to claim, the skill's role (`serving_climbers`). Computed once
    # per cycle by the player; the climber whose remaining climb a sibling
    # route is priced with. Empty on a failed ledger read (ruling T7b).
    fleet_climbers: dict[str, str] = field(default_factory=dict)
    # Every `L*` piece a sibling publishes: code -> (units asked, gain summed
    # over the publishers) (`CoordinationStore.sibling_demand_values`, one
    # read). The units a sibling climb is shared across, and
    # the pieces a crafter's role serves.
    fleet_board: dict[str, tuple[int, Fraction]] = field(default_factory=dict)
    # The board pieces this character's craft role serves (`fleet_pieces`,
    # computed once per cycle by the player from `role` and `fleet_board`):
    # the crafter's joint objective beside its own `L*` pieces.
    fleet_pieces: tuple[FleetPiece, ...] = ()

    # The live party lease naming this character as a MEMBER
    # (`CoordinationStore.party_lease_for`, read once per cycle by the player
    # and threaded here as DATA, like `supply_target`): the `PARTY_JOIN`
    # guard fires on it and `JoinPartyGoal` holds on its tile
    # (docs/PLAN_group_fights.md increment 4). None on a single-character run.
    party_hold: PartyLease | None = None

    # The monster the committed intention FIGHTS next: the first Fight in its
    # cached plan, or None when the intention fights nothing (2026-10-06). The
    # CRAFT_POTIONS guard sizes its stock for this monster and nothing else.
    # Live Lor: sized for `primary_combat_target` — the first winnable in-band
    # monster, `rat`, which Lor never fought — the guard gathered ~258
    # sunflowers in three hours for potions the server drank in cow and wolf
    # fights Lor won anyway.
    fight_monster: str | None = None

    # The consumable loadout chosen against the fight ahead (`fight_monster`,
    # else `combat_monster`): `best_loadout.fight_ahead_loadout`, read ONCE per
    # cycle by the player (docs/PLAN_consumable_utility.md increment 5). The
    # one authority every consumable decision reads — the CRAFT_POTIONS guard,
    # every fight step's potion and food prep, the fleet floor's need and the
    # keep authority's carry. None with no fight ahead, and on every caller
    # that does not choose one: nothing is stocked for it.
    loadout: ChosenLoadout | None = None

    # The grind target stands only on consumables (USER 2026-10-10, "loadout
    # picks the monster"): `combat_monster` is the band's pick on its best
    # loadout, and on BARE gear the cascade names no monster at all — no
    # winnable task monster, nothing in the band winnable bare, no windowed
    # pick. The gear decisions (`decisions.root.IsAFightBlockingMe`) read this
    # and never `loadout`, so a potion-propped win never hides a gear upgrade.
    # False (the default) whenever bare gear has a fight, or there is no target.
    # Since the gear objective names the grind target (`gear_objective` below)
    # nothing sets it: the band pick it described is no longer the target, and
    # a target that wins only on potions is `combat_risky` too.
    combat_propped: bool = False

    # The grind target wins below SECURE_WIN (USER 2026-10-15: below 75% we
    # probably need better gear; `combat.secure_win`, asked at max HP on bare
    # gear, `combat.unpotioned`): like a
    # propped target it does not hide a gear upgrade from
    # `decisions.root.IsAFightBlockingMe`. It is still fought when no gear is
    # to be built. False whenever there is no target.
    combat_risky: bool = False

    # Whether the held items task pays enough to defer the grind (spec
    # 2026-10-14 items-task-pays §2, `held_task_pays.held_task_pays`): its
    # gold or drops verdict, or skill XP the DAG demands at a better rate than
    # the grind's character XP. Priced ONCE per cycle by the player, because
    # the level step reads it up to four times a cycle and the price walks the
    # task and the loadout chooser. False (the default) with no items task, no
    # combat target, or a task that does not pay.
    held_task_pays: bool = False

    # The cycle's gear objective `(L*, m*)` (spec 2026-10-18 §2.4,
    # `gear_objective.gear_objective`), computed ONCE per cycle by the player
    # from this context's pricing fields, before the grind target is set. While
    # it is not held no fight is chosen for XP (§6.2), so `combat_monster` is
    # `m*` only when it is held, else the held monsters task's monster or None.
    # None when no monster pays, and on every caller that does not compute it.
    gear_objective: GearObjective | None = None

    # The learned seconds of a fight and of one planner action (spec
    # 2026-10-18 §2.9, rulings CA/CC): the fleet's recorded fights and a
    # `/my/logs` bootstrap, fitted once per cycle by the player
    # (`learning.fight_seconds_model`), or the committed live capture offline.
    # None on a context that never prices time: reading one there raises
    # (`timing` / `action_seconds_of`), never a constant.
    fight_seconds: FightSecondsModel | None = None
    action_seconds: Fraction | None = None

    # The fleet's drop evidence this cycle (spec 2026-10-18 §2.8, ruling
    # T16a): the ONE drop model the acquisition walk, the obtain model's gather
    # order and (through the actions that carry the same value) the planner and
    # every source picker read. Built once per cycle by the player from the
    # learning store; `LearnedDrops.empty()` (the API prior) on an offline
    # world (`fight_seconds_model.offline_context`) and on each store-less
    # site, passed explicitly. None here and on NO_PROFILE_CONTEXT (ruling
    # T16b): reading it then raises (`drops`), so no live path can price the
    # prior by inheriting a default.
    learned_drops: LearnedDrops | None = None

    # The previous executed action came back HTTP 497, the server's "inventory
    # is full" (Task 13e): the server's word overrides the slot model, so the
    # arbiter clears the bag before the next plan (`ai/bag_clear`). Set by the
    # player from its last outcome; False on every offline and first cycle.
    bag_refused: bool = False

    # The chosen root's requirement closure (`strategy_driver.chosen_root_closure`),
    # bound by `StrategyArbiter.select` with `step_profile`: the full-bag clear
    # keeps these stacks whole (`bag_clear.related_codes`). Empty on every ctx
    # built before the arbiter binds it (the root walk's own step checks).
    root_closure: frozenset[str] = frozenset()

    def drops(self) -> LearnedDrops:
        """This cycle's drop evidence; raises when this context has none."""
        if self.learned_drops is None:
            raise ValueError("this context carries no drop evidence")
        return self.learned_drops

    def timing(self) -> FightSecondsModel:
        """The learned fight-seconds model; raises when this context has none."""
        if self.fight_seconds is None:
            raise ValueError("this context carries no learned fight seconds")
        return self.fight_seconds

    def action_seconds_of(self) -> Fraction:
        """The learned seconds of one planner action; raises when this context
        has none."""
        if self.action_seconds is None:
            raise ValueError("this context carries no learned action seconds")
        return self.action_seconds


NO_PROFILE_CONTEXT = SelectionContext(
    bank_accessible=True,
    bank_required_level=0,
    bank_unlock_monster=None,
    initial_xp=0,
    # ONE COIN, matching production's own default
    # (`player.py`: `get_fleet_learned_int("task_exchange_min_coins", 1)`), not zero.
    # `_fires(TASK_EXCHANGE)` is `coins >= this`, so zero read `coins >= 0` —
    # true for every character alive — and the rung fired in 44 of 44 offline
    # scenarios, all of them coinless. The goal it built was satisfied on
    # construction and the arbiter skips satisfied goals, so nothing was
    # mis-selected; what it cost was every offline measurement of the
    # discretionary band carrying a rung with nothing to do. The taskmaster
    # cannot exchange fewer than one coin under any learned value, so 1 is the
    # floor rather than a guess.
    task_exchange_min_coins=1,
    combat_monster=None,
)
"""The "no active goal profile" stand-in, and the ONLY default any keep/deposit
consumer may use.

The in-bag keep ladder reads exactly ONE ctx field — `step_profile`
(GOAL_MATERIALS); `gear_keep` is read only by the OWNED ladder. Every other field
here is a guard-tier runtime flag the keep authority never touches, so this
instance is inert for keep purposes: it says "no step profile, no gear profile",
which is precisely what the `profile_codes=frozenset()` default it replaces meant.
It is NOT a substitute for the player's real context — the guard tier always
threads its own, and `StrategyArbiter.select` binds `step_profile` onto it before
any deposit decision is taken."""
