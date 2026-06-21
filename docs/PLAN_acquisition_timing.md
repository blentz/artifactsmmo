# PLAN: efficiency weighting (#16) + acquisition timing (#14)

Coupled tasks — #14's chosen benefit metric (per-stat efficiency rate × remaining
levels) is exactly #16's model, so they ship as one coherent feature. User
decisions (2026-06-20): benefit = Σ stat_i × efficiency_rate_i × (50 − level);
placement = modulate the objective gear_gap by a horizon factor.

## Motivation

Post-#12/#13 the rune/bag/artifact slots are targeted, reachable, funded, proved.
But the bot has no notion of WHEN a non-combat acquisition is worth its gold +
cooldown cost, and `equip_value` sums all stats 1:1 — a +35 inventory_space bag
scores like +35 attack, ignoring that a bag compounds (fewer bank trips for 40
levels). User: "good strategy = capitalize on non-combat efficiencies + optimal
acquisition timing."

## Architecture decision (isolate the proved combat core)

`equip_value` is the COMBAT scorer, proved via EquipValueAugmented + GearPolicy +
PurposeRouting + the Extracted/EquipValue bridge, and consumed by 10 modules
(decide_key, strategy, prerequisite_graph, inventory_caps, upgrade_selection, …).
DO NOT reweight it — that ripples through the entire combat-decision proof chain.

Instead introduce a SEPARATE `strategic_value(stats, level)`:
* combat stats (attack/resistance/hp/…) keep weight 1 (so combat slots are
  unchanged vs equip_value ordering);
* efficiency stats (inventory_space, wisdom, prospecting, haste) are weighted by a
  DERIVED efficiency rate (below);
* #14: multiply the whole thing by a horizon factor `(50 − level) / 50` (or
  similar), so timing emerges — high early, decays to ~0 near 50 (won't buy a rune
  at L49).

`strategic_value` is used ONLY in `ObjectiveGap.gap` (cross-slot priority) and the
#14 timing — NOT in the combat loadout / within-slot best-item selection (those
stay on the proved `equip_value`).

## The crux: efficiency rates MUST be derived from API data, not invented

CLAUDE.md: "Use only API data or fail with an error." So the per-stat efficiency
rates cannot be hardcoded multipliers. Derive them:

* **inventory_space** → bank-trip cooldowns saved. A bigger bag means fewer
  deposit round-trips. Rate ≈ (bank round-trip cooldown) / (slots gained). Bank
  round-trip cooldown is derivable from map data (bank tile distance) + the
  per-move cooldown. NEEDS: a defensible "items produced per level" to convert
  slots→trips→cooldowns. ← OPEN: is there API data for production rate, or is this
  the one assumption we must surface? (Candidate: derive from gather/craft cooldown
  × typical actions per level — itself derived, not invented.)
* **wisdom** → xp multiplier. If the API exposes how wisdom scales xp, rate =
  Δlevels-saved. NEEDS: the wisdom→xp formula from API/openapi. ← VERIFY.
* **prospecting** → gather-yield/rate. Same: needs the prospecting→yield formula.
  ← VERIFY.
* **haste** → cooldown reduction. Likely a direct % from the effect value. ←
  VERIFY (cleanest — probably a literal rate).

ACTION before coding: audit openapi.json + live item/effect data for the
wisdom/prospecting/haste/inventory mechanics. If a formula exists, derive the rate;
if NOT, that stat's rate is the one honest modeling assumption to surface to the
user (don't invent silently).

## Proof boundary

* `strategic_value` as a pure core (`strategic_value_core.py` + extracted Lean):
  a nonneg-int weighted sum. Prove it nonneg (so the gap bounds hold) and
  monotone in each stat.
* `ObjectiveGap.gap` with `strategic_value` in place of `equip_value` for
  `_item_value`: the proved `0 ≤ gap ≤ denom` and `is_complete` results hold for
  ANY nonneg int value function (the proofs are parametric in the value), so the
  Objective.lean lockstep is light IF strategic_value stays nonneg int.
* #14 horizon factor: a rational in (0,1]; modulating gear_gap numerator by it
  preserves `0 ≤ scaled_gap ≤ gap ≤ denom` (bound holds) and `scaled_gap = 0 ⟺
  gap = 0` for factor > 0 (is_complete preserved). At level = 50 the factor is 0 —
  but the char is done, so the degenerate is_complete reading is benign (verify /
  carve the L50 edge).
* Differential + mutation for strategic_value and the horizon factor.
* equip_value is an EXTRACTED core — if any change touches it, regenerate
  Formal/Extracted/EquipValue.lean (the #13b drift lesson). strategic_value is a
  NEW extracted core from day one (project_mechanical_extraction policy).

## Phases

1. **Ground the efficiency model** — audit openapi/live data for wisdom/
   prospecting/haste/inventory mechanics; derive each rate or surface the one
   honest assumption. (No code; produces the rate definitions.)
2. **strategic_value core** — pure module + extracted Lean + nonneg/monotone
   proofs + differential + mutation.
3. **#16 wire** — ObjectiveGap.gap uses strategic_value for cross-slot priority;
   adapt Objective.lean (parametric value); unit tests; gate.
4. **#14 horizon modulation** — multiply gear_gap numerator by horizon factor;
   Objective.lean bound/is_complete preserved (factor∈(0,1]); L50 edge; tests; gate.
5. Adversarial review + ≥100% coverage.

## Phase 1 grounding — RESULTS (2026-06-20, openapi.json + live cache)

* **wisdom** ✓ DERIVED: openapi "Wisdom increases the amount of XP gained from
  fights and skills (1% extra per 10 wisdom)" → rate = wisdom × 0.1% XP. Converts
  to levels-saved (fewer fights to level).
* **prospecting** ✓ DERIVED: openapi "Prospecting increases the chances of getting
  drops from fights and skills (1% extra per 10 prospecting)" → rate =
  prospecting × 0.1% drop chance. Converts to fewer fights/swings per needed drop.
* **haste** ✗ NOT IN API: item effect desc = "Adds N Haste… reduces the cooldown
  of a fight." NO rate (%/pt) documented anywhere in openapi or the effect data.
  Per "use API data or fail" we must NOT invent 1%/pt. → DECISION NEEDED: exclude
  haste from the efficiency model (keep weight 1, unchanged) until a rate is
  confirmed, OR confirm the rate empirically.
* **inventory_space** ✗ PARTIAL: the bag stat = literal added slots (no formula
  needed there). But slots→bank-trips→cooldowns-saved needs a PRODUCTION-PER-LEVEL
  figure (how many items/level fill the bag) that is NOT API data. Bank round-trip
  cooldown IS derivable (map distance × move cooldown). → DECISION NEEDED: the
  production-rate assumption (or derive a proxy from gather/craft cadence).

So 2/4 rates are cleanly API-derived (wisdom, prospecting); 2/4 (haste,
inventory_space) hit the no-invented-defaults wall and need a user decision.

## Phase 1 decisions RESOLVED (user 2026-06-20)

* **haste** → CONFIRM EMPIRICALLY (live probe). Not in API; measure it:
  1. equip a known-haste item (effect value N), record a fight's cooldown `cdN`;
  2. unequip, record the same fight's cooldown `cd0`;
  3. rate per point = `(cd0 − cdN) / (cd0 × N)`.
  Needs a LIVE character run (perturbs the real character) — author a one-shot
  probe script; do NOT hijack the playing bot without the user's go-ahead. Until
  measured, haste stays weight 1 (excluded), so #16 can ship on wisdom +
  prospecting + inventory and fold haste in once the rate is known.
* **inventory_space** → PROXY from gather/craft cadence, all API-derived in the
  existing COOLDOWN-COUNT currency (craft_vs_buy already counts cooldowns as
  actions, not seconds):
  - bank deposit cooldown = 3s × distinct items (openapi) → ~1 cooldown-action per
    bank trip in the action-count model;
  - items/level ≈ xp_to_level / xp_per_action (xp curve + action xp, API);
  - trips_saved per Δslot ≈ Δslots / items_per_trip;
  - inventory rate = trips_saved × bank_roundtrip_cooldown (distance × move
    cooldown, map-derived). Stays within "use API data".

## Status
* Design + architecture decided; Phase 1 grounding + decisions DONE.
* Phase 1b DONE (merged): scripts/probe_haste.py — empirical haste-rate probe.
  R fights item-ON vs item-OFF, rate = (cd0−cdN)/(cd0×N); predict_win safety gate +
  lost-fight abort + loadout restore + combat-stat-confound warning; coverage-
  omitted (live-I/O). AWAITING the user's live run for the haste rate.
* Phase 2 DONE (branch feat/strategic-value, 49e56ea — full gate green):
  `strategic_value_pure` pure core (tiers/strategic_value.py) extracted to
  Formal/Extracted/StrategicValue.lean, proved against hand model
  Formal/StrategicValue.lean (nonneg + 5 per-stat monotonicity + 2 witnesses),
  transferred via Bridges9; Oracle `strategic_value` runner + differential
  (exact-int agreement/nonneg/monotone) + 5 mutations (all killed) + Manifest +
  Contracts pins + unit tests; 100% coverage. The five inputs (combat_raw +
  wisdom/prospecting/inventory_space/haste) each take a CALLER-SUPPLIED nonneg-int
  weight; combat_raw carries one dominant weight so combat ordering is preserved.
  GOTCHA: mutation-kill output ("1 failed … skip HP_CRITICAL / reverse
  MIRROR_LADDER_ORDER") is EXPECTED, not a baseline break — gate.sh runs
  differential before mutation under set -e, so "ALL GATE PARTS PASSED" is the
  real green signal (a `| tail` on the gate invocation masks gate.sh's own exit).
* Phase 3a was INERT + REVERTED. It wired ObjectiveGap.gap → strategic_value, but
  gap()/ObjectiveGap has NO live consumer — the whole Tier-1 objective-distance
  chain (gap → personality.weighted_remaining → objective_completion) is shadow/dead
  in the live planner (logged: project_dead_tier1_objective_gap; user: investigate
  separately). The LIVE cross-slot gear priority is StrategyEngine._equip_gain =
  max(0, equip_value(item) − equip_value(current)), the single source for both the
  _marginal rank score AND the kernel-proved decide_key protection tiebreak.
* Phase 2 strategic_value core + wrapper RETAINED (proved, gated) — they feed the
  real lever next.
* Phase 3b-prereq DONE (merged): LearningStore.action_class_cost — learned
  per-action-TYPE cooldown (FightAction/MovementAction/DepositAllAction medians,
  warmup-gated, default fallback). The API has NO static fight-cooldown formula, so
  the cooldown-seconds currency READS GAMEPLAY (user direction 2026-06-21). The
  recording already existed (action_class + actual_cooldown_seconds per cycle).
* DECISIONS (user 2026-06-21): common currency = COOLDOWN-SECONDS SAVED, learned
  from gameplay (not assumed); inventory proxy ÷ items_per_trip(=inventory_max);
  wire-now/full-rates-next; #16 lever = _equip_gain; dead Tier-1 = separate issue.
* REAL #16 WIRING DONE (merged 079978f, full gate green): StrategyEngine._equip_gain
  now uses strategic_value (was equip_value) — the live source for the gear
  _marginal score AND the decide_key protection tiebreak. GEAR_EQUIP_SCALE rescaled
  ×STRATEGIC_SCALE(1000) so combat marginals keep ~[0,1] gradation. Combat ordering
  preserved (combat-dominant). KEY: decide_key proof/differential/mutation UNTOUCHED
  — protection is an abstract int in DecideKey.lean (negProtect), so the value-source
  swap never reaches the comparator (step 3 of the old plan was a non-issue; only doc
  comments updated). within-slot SELECTION (target_gear/near_term_gear) stays
  equip_value. Net live effect: wisdom/prospecting gear down-weighted ~1000× (openapi
  0.001) so XP/drop artifacts no longer rank like attack; bags at parity pending 3b.
* PHASE 3b DONE (merged 57b3fd9, full gate green). Built per the design below.
  Shipped: LearningStore.action_class_fraction (action-mix freq); strategic_weights
  (state, history) → learned cooldown-seconds-saved weights (wisdom/prospecting =
  0.001×fight_cd×f_fight; inventory = roundtrip_cd/inventory_max×f_trip; haste = 0
  until probe); strategic_value wrapper efficiency-budget CAP (combat dominance
  structural); history threaded _equip_gain→_marginal→_value←decide (cold →
  combat-only). Proved core unchanged. 100% cov.
* PHASE 3b DESIGN (locked; user 2026-06-21: efficiency sub-budget below combat;
  build full). Combat and efficiency are DIMENSIONALLY incommensurate (combat =
  stat-points×SCALE; efficiency = cooldown-seconds). Resolution: combat keeps the
  dominant SCALE weight; the efficiency block is CAPPED at < 1 combat-point so it
  orders gear only among efficiency-bearing/empty slots and never outranks a real
  combat upgrade. The cap lives in the WRAPPER (strategic_value), NOT the proved
  core (strategic_value_pure stays a plain weighted sum — no Lean/bridge/oracle/diff
  change). Wrapper: total = combat_raw×combat_weight + min(EFFICIENCY_BUDGET,
  Σ efficiency_stat × seconds_rate_fp).
  FREQUENCY (the crux): per-event seconds bias toward inventory (wisdom helps every
  FIGHT, a bag every BANK-FILL), so rates must be frequency-weighted. The char-level
  xp curve is NOT tracked (skill_max_xp is skill-keyed) → fights/level unavailable.
  Use LEARNED ACTION-MIX instead: f_fight/f_trip = fraction of recent cycles of each
  action_class (needs a new LearningStore.action_class_count, sibling to
  action_class_cost). Then:
    - wisdom/prospecting seconds_rate = 0.001 × learned_fight_cd × f_fight
    - inventory seconds_rate/slot = (learned bank roundtrip cd / inventory_max) × f_trip
      (roundtrip cd ≈ 2×action_class_cost("MovementAction") + action_class_cost(deposit))
    - haste = 0 until the live probe returns its rate (no invented rate)
  All cooldowns LEARNED (action_class_cost); cold fallback = DEFAULT_FIGHT_CYCLES /
  defaults → efficiency ≈ 0 (parity removed) so behavior degrades to combat-only
  gear priority when unlearned.
  BUILD STEPS: (1) action_class_count accessor + test; (2) strategic_weights(state,
  history, game_data) deriving the fixed-point weights + budget; (3) wrapper cap +
  thread history through _equip_gain/_marginal (history=None → cold/zero-efficiency,
  backward-compatible); (4) strategy/wrapper unit tests + mutation + gate.
* (Phase 4) #14 horizon factor (50−level)/50 multiplying the efficiency block so
  acquisition is front-loaded (efficiency rates are per-event; horizon scales total
  remaining benefit). Haste folds in once the probe returns its rate.
* #12/#13 complete + merged. #15 (currency arbitrage) independent, still queued.
