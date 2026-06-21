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
* NEXT: (Phase 3) ObjectiveGap rewire — derive the weights from game_data
  (wisdom×0.001, prospecting×0.001, inventory×cadence-proxy, combat dominant,
  haste×1 until probe) and use strategic_value for _item_value cross-slot priority;
  adapt Objective.lean (parametric value); (Phase 4) #14 horizon factor.
* #12/#13 complete + merged. #15 (currency arbitrage) independent, still queued.
