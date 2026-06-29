# Sub-project C — Loadout Profiles + Bank-Aware Dedup — Design

**Status:** approved (brainstorm 2026-06-28) · **Epic:** Holistic Gear-Loadout
Architecture (`2026-06-28-gear-loadout-architecture-design.md`, on main).
**Branch:** `feat/gear-loadout-profiles` (off main = sub-project B merged, tip `5eaec02b`).
**Build order:** sub-project 4 of 5 (A ✅ → ruler ✅ → B ✅ → **C** → D).

## Why

Gear keep/recycle/deposit/sell protection is today anchored on `objective.target_gear` /
`target_tools` (the aspirational endgame BiS sheet) flowing through `inventory_profile` →
`profile_codes` → bank keep-set, `recycle_surplus` protected set, `select_bank_deposits`,
accumulation-sell, and `factory` recycle-exclusion. This over-protects (the whole endgame
sheet's recipe closure) and has no notion of which loadouts the bot *actually wears*. C replaces
the gear portion of that protection with **per-task loadout profiles** the bot auto-records, plus
a **dedup** that holds shared gear once, and wires the freed bank-space signal into expansion
timing.

## Scope (approved decisions)

- **Replace, don't augment.** The protected keep-set's GEAR portion becomes the **active-profile
  loadout union + the in-flight upgrade (+1 spare)**. `target_gear` stays the PURSUIT target
  (what to craft next) but stops being a blanket protection set. Un-profiled, not-in-flight gear
  becomes reclaimable. (Far-future stashed gear is already banked by the existing
  level-distance ceiling, so it isn't recycled.)
- **Active = current-objective tasks ∪ recent-window tasks.** Not current-only (avoids
  re-craft churn on task swing-back), not all-persisted (avoids hoarding).
- **Bank-space cost wires into bank-expansion timing.** Feed a `used` floor into
  `should_expand_bank` so the bot proactively expands when active-profile gear would overflow the
  bank.
- **Persisted profiles** (`LearningStore`), not recompute-only — a stored profile is a stable
  protected set across mid-swap inventory churn and the foundation D refines.

## v8 grounding (verified 2026-06-28)

Bank cost/capacity are **live-sourced**, never hardcoded: `_build_bank` (game_data.py:1124-1129)
ingests live `BankSchema.slots` (currently 50) → `bank_capacity` and
`BankSchema.next_expansion_cost` (currently 3500, server-escalating) →
`next_expansion_cost`; `expand_bank.py:46-48` feeds those exact live values into
`should_expand_bank`. The 20-slot increment matches the v8 openapi. API client verified current:
vendored `openapi.json` 8.0.0 == live server 8.0.0 (identical 109 paths / 264 schemas). C's
wiring adds only a `used` floor — it does NOT touch the cost model.

## Architecture

Five units:
- **Profile store** (`LearningStore`): `LoadoutProfileObservation` table `(character, task_key) →
  loadout` (serialized `dict[slot, code]`), mirroring `CraftYieldObservation`. `task_key` =
  `"combat:<monster_code>"` / `"gather:<skill>"` — the keys `OptimizeLoadoutAction` already uses.
  `record_loadout_profile(task_key, loadout)` upsert; `loadout_profiles() -> {task_key: loadout}`.
- **Auto-creation** (impure hook): when the bot performs a task, upsert `(task_key,
  pick_loadout(purpose))` — the profile tracks the best owned loadout for that task over time and
  pre-stages D. Best-effort `record_*` contract (log+swallow, never crashes a live action; no
  `except Exception`).
- **Active determination**: `active_profiles` = profiles whose `task_key ∈ (current-objective
  tasks ∪ recent-window tasks)`. Current-objective tasks = `SelectionContext.combat_monster` +
  the gather skills the active goal needs; recent-window = `task_key`s derived from recent
  `Cycle.selected_goal` (reuse `recent_goal_cycles`).
- **Dedup core** (pure, proved): `gear_demand(active_profiles) -> dict[code, int]`.
- **Bank-space-cost core** (pure, proved): `bank_space_cost(active_profiles, equipped) -> int`.

## The proved cores

- **`gear_demand(active_profiles) -> dict[code, int]`** = for each gear code, the **MAX over
  active profiles** of its count within that profile's loadout (a profile can hold a code twice
  only for rings). One loadout is worn at a time, so shared gear is held once: two profiles each
  using `copper_dagger` ⇒ `demand = 1`. Role theorems:
  - **(a) characterization** — `demand(code) = max over active p of count(code, p.loadout)`.
  - **(b) dedup bound** — `demand(code) ≤ max_p count(code, p)` (≤ 2 for dup-allowed rings, ≤ 1
    otherwise) — the load-bearing "held once" fact.
  - **(c) monotone** — adding an active profile never decreases any demand.
- **`bank_space_cost(active_profiles, equipped) -> int`** = `|{distinct gear code in any active
  profile} − {currently equipped codes}|`. Role theorems: nonneg; monotone in profiles; bounded
  by total distinct active-profile gear.

## Bank-expansion wiring

Feed `used' = max(current_bank_used, bank_space_cost(active_profiles, equipped))` into
`should_expand_bank(used', capacity=live slots, gold, cost=live next_expansion_cost, reserve,
trigger_num, trigger_den)`. `should_expand_bank` is already proven monotone in `used`
(`expand_stable_under_more_fill`), so the floor only ADDS expansion firing — the bot expands
proactively when active-profile gear would overflow the bank, never suppresses a needed
expansion, and never violates the reserve gate. Lean: a small lemma that the `max(used, cost)`
floor preserves the threshold + reserve guarantees (rides the existing monotonicity).

## Keep-economy consumer migration (the "replace")

The GEAR portion of every protected set switches from `target_gear`/`target_tools` recipe-closure
to the **active-profile gear-demand set + in-flight upgrade (+1 spare)**. Non-gear protection
(`tasks_coin`, `task_code`, HP consumables, crafting/task recipe materials) is UNCHANGED. Sites:
- `inventory_caps` equippable keep / dominance (`useful_quantity_cap` equippable component) →
  keep up to `gear_demand(code)` for active-profile gear; un-profiled gear is no longer kept at 1
  (becomes reclaimable when not in-flight).
- `bank_selection._keep_codes` (the gear part), `recycle_surplus` protected set,
  `select_bank_deposits`, accumulation-sell gear protection, `factory` recycle-exclusion → read
  the active-profile gear set instead of `ctx.target_gear | ctx.target_tools`.
- `inventory_profile` / `active_profile` / `SelectionContext` carry the active-profile gear set
  (computed once per cycle), the way they carry `target_gear` today.

This **subsumes the `_ARMOR_TYPES` / `defensive_gear_types` keep usage** and reconciles
`InventoryCaps` / `RecycleProtection` onto ONE protected-set definition. The in-flight upgrade
(the objective's currently-pursued gear craft) is protected with +1 even before it appears in a
profile, so an upgrade mid-craft is never recycled.

## Formal lockstep

- `Formal/LoadoutProfiles.lean`: `gearDemand` (MAX fold) + `bankSpaceCost` + their role theorems
  (∀ inputs); a lemma `shouldExpandBank_floor_preserves` that `used' = max(used, cost)` keeps the
  reserve + threshold guarantees of `BankExpansionTiming.shouldExpandBank`.
- Preserved UNCHANGED (purpose/profile-independent): `RealizableLoadout`, `LoadoutProjection`,
  `OwnedCount` — verify their `Contracts` pins still elaborate.
- `Contracts.lean` exact pins + `Manifest.lean` roster + `Audit.lean` `#print axioms` for every
  new role theorem. Differential: `gear_demand` / `bank_space_cost` ≡ oracle on random profile
  sets (NO `unique=True`). Mutation: drop the MAX in `gear_demand`, the equipped-subtraction in
  `bank_space_cost`, the `max` floor in the expansion wiring — each killed.

## Module layout

- `ai/loadout_profiles_core.py` (pure, extracted, proved): `gear_demand`, `bank_space_cost`.
- `ai/loadout_profiles.py` (active-set resolution: reads the store + current/recent context →
  active profiles → gear set).
- `LearningStore`: `LoadoutProfileObservation` table (models.py) + `record_loadout_profile` /
  `loadout_profiles` (store.py).
- Auto-creation hook (player/strategy, where a task cycle completes).
- Consumer migration across `inventory_caps`, `bank_selection`, `recycle_surplus`,
  `inventory_profile`, `factory`, `guards`/`strategy_driver`, `expand_bank`.
- Layering: cores are leaves (plain data); `loadout_profiles.py` imports the store + context, not
  the consumers.

## Testing & rollout

- **Dedup**: 2 active profiles sharing a code → held once (demand 1); rings → 2.
- **Reclaim**: gear in NO active profile and not in-flight becomes recyclable/sellable/bankable
  (was protected before).
- **In-flight protection**: a gear upgrade mid-craft (in `target_gear` pursuit, not yet profiled)
  is NOT recycled (+1 spare).
- **Bank expansion**: fires when active-profile gear would overflow the bank (used-floor), using
  the LIVE v8 cost/capacity; never fires below reserve.
- **No non-gear regression**: tasks_coin / task_code / consumables / recipe materials still
  protected exactly as before (regression-locked).
- `record_loadout_profile` best-effort (log+swallow). Full suite ≥ current bar (100%); full
  `formal/gate.sh` green; serialize gate/mutation vs live `play`; re-run `extract_lean.py` after
  source moves.

## Out of scope / non-goals (→ D and follow-ons)

- The LEARNED winning loadout + `predict_win`-vs-outcome refinement — sub-project **D** (C
  records the best *owned* loadout per task; D refines by combat result, keyed on the same
  `(character, task_key)`).
- Modeling the 9 carved rune abilities (the "Player rune abilities" follow-on).
- A user-facing named-profile CLI (auto profiles only, per the epic non-goals).
- Re-deriving the bank-expansion trigger ratio / reserve (kept as-is; C only adds the used-floor).
