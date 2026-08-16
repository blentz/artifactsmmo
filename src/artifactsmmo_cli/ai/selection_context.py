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
the one exception is `TurnIn` below, a leaf pure-data class (`ai.currency_turnin`
imports only stdlib) that carries no cycle risk of its own.
"""

from dataclasses import dataclass, field

from artifactsmmo_cli.ai.currency_turnin import TurnIn


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
    # The OWNED SKILLS of the specialization role this character holds THIS
    # cycle (`role_catalog.role_skills(role)`), or the empty frozenset when it
    # holds none — every single-character run, and any cycle whose lease is
    # not held. Populated by the player's per-cycle coordination block from
    # `GamePlayer._role` (resolved against `role_catalog.ROLES_BY_NAME`
    # there, not here — this module imports nothing from the package, see the
    # module docstring), the same seam as `supply_target`: the role is a
    # per-cycle player runtime fact, which is exactly what this context
    # carries, so the tree reads it here rather than through a second
    # `decide`/`decide_tree` parameter.
    #
    # Carrying owned SKILLS rather than the role NAME is deliberate: it lets
    # `progression_tree._role_map` turn this straight into the per-candidate
    # role-fit multiplier without resolving a name against `ROLE_CATALOG`
    # itself, which would re-import `role_catalog` into `ai.tiers` and revive
    # the circular import `role_catalog -> tiers.skill_classes ->
    # tiers.__init__ -> tiers.strategy -> tiers.progression_tree ->
    # role_catalog` (2026-08-01 fix). `role_skills(role)` is never empty for a
    # real `Role`, so the empty frozenset is an unambiguous "no role" sentinel
    # — `_role_map` returns `{}` for it, the inert four-factor product.
    role_skills: frozenset[str] = field(default_factory=frozenset)
    # {item_code: quantity} of BANK stock a SIBLING has already committed to
    # withdrawing this cycle — `CoordinationStore.sibling_bank_claims`, read
    # once per cycle by the player's coordination block and threaded here as
    # DATA, the same seam as `supply_target` and `role_skills`. Empty (the
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
    # `supply_target` and `role_skills`. Empty (the default) on every
    # single-character run and whenever no coordination store is attached.
    #
    # This is the signal that distinguishes "a sibling asked but could gather
    # it itself" (not worth pausing for) from "nobody nearby can make this"
    # (the request the SUPPLY rung exists to serve) — see
    # `MaterialDemand.self_servable`'s docstring for why the requester's own
    # ability, not just the quantity, has to ride on the row.
    asymmetric_demand: frozenset[str] = field(default_factory=frozenset)


NO_PROFILE_CONTEXT = SelectionContext(
    bank_accessible=True,
    bank_required_level=0,
    bank_unlock_monster=None,
    initial_xp=0,
    task_exchange_min_coins=0,
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
