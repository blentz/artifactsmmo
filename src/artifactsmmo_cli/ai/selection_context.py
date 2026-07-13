"""`SelectionContext` — the per-cycle player runtime flags the pure selection
cores read (guards, keep authority, deposit selection).

It lives in its OWN module, below every consumer, because the keep authority
(`ai/inventory_keep.py`) and the deposit selector (`ai/bank_selection.py`) both
need it while `ai/tiers/guards.py` — its historical home — imports THEM. Keeping
the dataclass in `guards` made `guards -> bank_selection -> inventory_keep ->
guards` a cycle the moment deposit started asking the keep authority how many
copies it may bank. `tiers.guards` re-exports the name, so every existing
`from artifactsmmo_cli.ai.tiers.guards import SelectionContext` still resolves.

Pure data: no behavior, so this module imports nothing from the package.
"""

from dataclasses import dataclass, field


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
