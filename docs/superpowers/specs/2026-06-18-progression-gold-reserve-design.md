# Progression gold reserve — design

Replace the flat `GOLD_RESERVE = 500` with a **calculated per-character
progression reserve**: gold kept available for near-term (next 1-2 levels)
progression purchases, with deduction accounting so buying a reserved item
fulfills (not blocks) its own reservation. Audit #9 of
`docs/PLAN_calculate_not_hardcode.md`.

## Design decisions (settled in brainstorming 2026-06-18)

1. **Role** — a calculated protective FLOOR (same role as today's GOLD_RESERVE),
   not a new buying behavior. Plus deduction accounting: a purchase matching the
   reservation criteria is deducted from the reservation.
2. **Reserved categories** — gear upgrades + crafting-unlock items + boss-odds
   items. (Boss is a deferred stub this version — see Out of scope.)
3. **Horizon** — fixed: items usable at character `level .. level+2`.
4. **Cost basis** — only targets the bot would BUY (no craft path, or
   `craft_vs_buy` says buy), priced `min(npc_sell_price, ge_best_buy_order)`.
   Craftable-now targets contribute 0 (they cost gathering/time, not gold).
5. **Gate scope** — all three buy-gates honor the reserve, uniform: gathering
   material-buys, ge_fill_sell resale-buys, bank expansion.
6. **Formal** — the reserve arithmetic + deduction-accounting affordability is a
   proven pure core (Lean model + differential + mutation). The impure
   target-identification/pricing stays unproven glue.

## Architecture (Approach A: pluggable sources + proven core)

```
buy-gates (gathering / ge_fill_sell / expand_bank)
    │  effective_floor(reserved_targets(state, gd), item_being_bought)
    ▼
progression_reserve.py        (impure: identify + price unmet targets)
    │  reserved_targets() = ⋃ category sources
    ├── gear source           (best per-slot upgrade ≤ level+2, buy-method)
    ├── crafting_unlock source(items lifting the next blocking craft gate)
    └── boss source           (STUB → {}; extension point)
    │  each yields {code: buy_cost} for UNMET, BUY-acquired targets
    ▼
progression_reserve_core.py   (PURE, PROVEN ↔ ProgressionReserve.lean)
    reserve_total / effective_floor / affordable
```

### Pure proven core — `ai/progression_reserve_core.py`

Operates on a `reserved: Mapping[str, int]` (code → buy-cost, already
deduped/priced by the impure layer), exact-int gold/price. Mirrors
`Formal/ProgressionReserve.lean`.

- `reserve_total(reserved) -> int` = `sum(reserved.values())`.
- `effective_floor(reserved, buying: str | None) -> int`
  = `reserve_total(reserved) - reserved.get(buying, 0)`  ← the deduction.
- `affordable(gold, price, reserved, buying) -> bool`
  = `gold - price >= effective_floor(reserved, buying)`.

**Proven theorem roles:**
- `floor-le-total`: `effective_floor(reserved, b) ≤ reserve_total(reserved)`
  (the deduction never increases the floor).
- `deduction-exact`: for `b ∈ reserved`,
  `effective_floor(reserved, b) = reserve_total(reserved) - reserved[b]`
  (a reserved item's own reservation is fully credited toward buying it — it is
  never blocked by itself).
- `nonreserved-protects-full`: for `b ∉ reserved`,
  `effective_floor(reserved, b) = reserve_total(reserved)` (discretionary buys
  protect the entire reserve).
- `floor-monotone`: `reserved ⊆ reserved'` (pointwise, same costs) ⇒
  `reserve_total(reserved) ≤ reserve_total(reserved')` (more unmet progression
  ⇒ higher floor; adding targets never loosens a discretionary gate).
- `affordable-antitone-in-floor`: a higher effective floor never turns an
  unaffordable buy affordable (monotonicity of the `≥` decision).

Exact integer arithmetic throughout (gold/prices are ints) — matches the
`CraftVsBuy.cheaper_acquisition` proven-core pattern.

### Impure layer — `ai/progression_reserve.py`

- `reserved_targets(state, game_data) -> dict[str, int]`
  Unions the category sources; for each unmet target in horizon
  `level..level+2`, includes it iff its acquisition is BUY (via
  `craft_vs_buy.acquisition_method`) and prices it `min(npc, ge)`. A code already
  owned/equipped, or craftable-now, is excluded (0 gold).
- `progression_reserve(state, game_data) -> int`
  = `reserve_total(reserved_targets(state, game_data))`. The single public
  reserve value (replaces the `GOLD_RESERVE` constant for callers that just want
  the floor).

Category sources (each `(state, game_data) -> dict[str,int]`):
- **gear** — for each combat slot, the best equippable usable at `≤ level+2` and
  not currently owned/equipped; if `acquisition_method` is BUY, add
  `{code: buy_price}`. Reuses `find_upgrade_target` / equipment scoring per slot.
- **crafting_unlock** — items required to lift the next blocking craft-skill gate
  within the horizon (the skill is below its near-term recipe-curve target).
  Reuses `skill_target_curve` / recipe gating. BUY-method + priced as above.
- **boss** — STUB returning `{}`. Documented extension point; built when the
  boss-pursuit machinery lands ([[project_roadmap5_discovery]]).

### Wiring (the three buy-gates)

Each replaces flat `GOLD_RESERVE` with the deduction-aware floor for the item it
is about to buy:
- `goals/gathering.py` acquisition gate — pass
  `effective_floor(reserved, item)` as the `reserve` into
  `acquisition_method` / `cheaper_acquisition` (the item may itself be reserved →
  deducted).
- `actions/ge_fill_sell.py` — `gold - price*qty < effective_floor(reserved, item_code)`.
- `goals/expand_bank.py` — the expansion is never a reserved gear code, so
  `effective_floor(reserved, None) = progression_reserve` (full floor).

`reserved_targets` is computed once per gate evaluation from the cycle's
`state`/`game_data`; pure, no caching needed beyond the call.

## Migration

`GOLD_RESERVE = 500` is removed. Open detail for the implementation plan: whether
to retain a small **minimum safety floor** (`max(progression_reserve, FLOOR)`)
so the bot never spends to zero when nothing is reserved, or trust the calculated
value (0 ⇒ spend freely). Lean toward a documented minimum floor to preserve the
original safety intent; decide in the plan.

## Testing

- **Pure core**: differential (Hypothesis ↔ oracle) over random reserved
  dicts/gold/price/buying; mutation runner with anchors; the 5 theorem roles
  manifest-rostered + Contracts-pinned.
- **Impure layer**: unit tests with `GameData` fixtures per category source
  (gear target found+priced; craftable-now excluded; buy-method gate; deduction
  when buying a reserved item; boss stub empty).
- **Wiring**: each gate's existing tests updated; new tests that a reserved-item
  buy is NOT blocked by its own reservation, and a discretionary buy IS blocked
  when it would breach the full floor.
- ≥90% coverage (project enforces 100%).

## Out of scope (deferred)

- **Boss-odds source** — stub only; needs the unbuilt boss-pursuit machinery to
  identify which items improve boss-fight odds (winnability + event/boss drops).
- **Active buying** — the reserve does not introduce new buy goals; it only
  re-values the existing buy-gate floor. (Explicitly rejected in brainstorming.)

## Soundness chain

`reserve arithmetic correct ⇐ (core ≡ Lean def, by differential) ∧ (Lean def
proves floor-le-total / deduction-exact / nonreserved-protects-full /
monotone)`. Impure target-identification is covered by unit tests, not proofs.
