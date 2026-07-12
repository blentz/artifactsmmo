# Inventory keep-unification — design

**Date:** 2026-07-12
**Status:** approved (design), spec pending user review
**Driver:** four instances of one bug class; the fourth is live in production.

---

## 1. Problem

Item protection is expressed two incompatible ways.

| Idiom | Type | Semantics | Consumers |
|---|---|---|---|
| **Cap** (correct) | `useful_quantity_cap(code, …) -> int` | keep N; `disposable = held - keep` | `sell_inventory`, `accumulation_sell`, `discard_overstock` |
| **Code-set** (defective) | `frozenset[str]` / `set[str]` | keep **every copy** | `bank_selection._keep_codes`, `deposit_inventory.profile_codes`, `guards.protected_gear_codes` / `recycle_protected_codes` / `_gear_protected`, `SelectionContext.target_gear` / `target_tools` / `near_term_targets`, `recycle_surplus.protected_codes` + `kit` |

**`frozenset[str]` cannot express "keep 1."** It can only express "keep all." Every protection reason added as a code-set therefore becomes an unbounded hoard. This is not a mistake repeated three times — it is what the type *means*. There are ~20 set-based protection sites.

### The four instances

1. **`gear_keep` blanket** — `recycle_protected_codes` returned every `gear_keep` KEY, so "keep 1" acted as "keep all 41" (`copper_helmet` hoard, trace 2026-07-05). *Fixed* by returning `frozenset()` when `gear_keep` is present — with a test literally named **"caps beat blankets."**
2. **Equipped-code skip** — a blanket `code in equipment` skip in `recyclable_surplus` shielded every spare of a worn code. *Fixed* by relying on `useful_quantity_cap`'s "keep ≥1 if equipped."
3. **Working-kit skip in recycle** — `code in kit → continue` shielded all 18 `copper_axe` + 7 `fishing_net` (live Robby 2026-07-12). *Fixed* `cd0e6d04` by making kit a cap **floor of 1**.
4. **Working-kit blanket in deposit — LIVE, UNFIXED.** `bank_selection._keep_codes` does `keep |= _best_gathering_tools(...)`, so `select_bank_deposits` refuses to bank a single one of the 17 `copper_axe` / 7 `fishing_net`. It also blanket-keeps `red_slimeball ×20` when only 2 are needed. **My recycle fix opened one exit from the bag; this one is still walled off.**

A fifth instance is guaranteed while the type survives. The migration to caps was *already started* (instance 1's fix) and abandoned; the right idiom exists but never displaced the wrong one.

### Aggravating factor (why the hoard is invisible, not merely tolerated)

The gathering tools (`copper_axe`, `fishing_net`) are simultaneously (a) best-in-skill **working kit** and (b) **weaponcrafting grind rungs**. So the skill grind manufactures more of precisely the items the protection rule makes untouchable. The pile is fed by design and drained by nothing.

---

## 2. Root cause

Two genuinely different questions were conflated into one "protection" concept:

* **"must stay in the BAG"** — don't bank it (task item, active goal's materials, kit tool pending equip). Banking is **reversible**; the item is still owned.
* **"must not be DESTROYED"** — don't recycle/sell/delete it (gear demand, recipe demand, task total). This is about **ownership**, and bank copies count toward it.

Collapsing both into code-sets is what turned *"I need this in my bag right now"* into *"never dispose of any copy, ever."*

---

## 3. Design

### 3.1 Two caps

```python
keep_in_bag(code, state, game_data, ctx) -> int   # copies that must stay in the BAG
keep_owned(code, state, game_data, ctx) -> int    # copies that must remain OWNED (bag+bank)

bankable(code)    = max(0, bag[code]   - keep_in_bag(code))    # deposit consults
destroyable(code) = max(0, total[code] - keep_owned(code))     # recycle/sell/delete consult
```

`total = bag + bank`. Both are plain quantities, so **a blanket is inexpressible**. *"Never DELETE what banking would have saved"* becomes true **by construction** instead of resting on a guard threshold (`_used_fraction` vs `_quantity_fraction`), which is the safety property the current design keeps re-losing.

### 3.2 Reason registry — the single place a protection reason may be added

Every reason is a named enum member contributing a **quantity** to one or both caps. Caps combine by `max()` over their reasons.

| `KeepReason` | Feeds | Quantity |
|---|---|---|
| `EQUIPPED` | owned | 1 |
| `WORKING_KIT` | in_bag | 1 (best tool per gathering skill — the ferry/equip race) |
| `ACTIVE_TASK` | both | remaining task quantity |
| `GOAL_MATERIALS` | in_bag | active objective-step goal's `needed` map |
| `GEAR_DEMAND` | owned | active-profile / per-slot demand (rings 2) + in-flight spare |
| `RECIPE_DEMAND` | owned | max recipe demand across known recipes + batch buffer |
| `CURRENCY` | owned | `KEEP_ALL` sentinel (`tasks_coin`) |

`KEEP_ALL` is the **only** way to express "keep everything": explicit, greppable, used once. A reason contributing a blanket must now say so out loud.

Each reason is a pure function `(code, state, game_data, ctx) -> int`, registered against the cap(s) it feeds. `useful_quantity_cap` is refactored into the `GEAR_DEMAND` / `RECIPE_DEMAND` / `ACTIVE_TASK` / `EQUIPPED` reasons rather than deleted — its logic is correct, only its callers' *parallel* set-based protection was wrong.

### 3.3 Consumers collapse

| Path | Today | After |
|---|---|---|
| `recycle_surplus` | cap **+** `protected_codes` **+** `kit` set | `destroyable ∩ recyclable` |
| `bank_selection` / `deposit_inventory` | `keep: set[str]` blanket, `profile_codes` | `bankable` |
| `accumulation_sell` / `sell_inventory` | cap (already correct) | `destroyable ∩ sellable` |
| `discard_overstock` | cap (already correct) | `destroyable`, last resort |

`disposal_route(recyclable, bank_ok, future_value) -> RECYCLE | DEPOSIT | DELETE` is unchanged — it decides *how* to shed surplus; the caps decide *what* is surplus. The two were previously tangled.

**Deleted:** `protected_gear_codes`, `recycle_protected_codes`, `_gear_protected`, `bank_selection._keep_codes`, `deposit_inventory.profile_codes`, `recyclable_surplus(protected_codes=…)`, and the `SelectionContext` blanket fields `target_gear` / `target_tools` / `near_term_targets` **in their protection role** (they survive only where they mean "acquisition target," not "protected"). ~20 sites; the bug class dies with the type.

---

## 4. Acceptance — inventory-management behavioral completeness census

Modeled on the crafting census (`audit/craft_completeness.py` + `scripts/gen_craft_completeness.py --check`, which drove `planner_bug` to 0).

**Oracle = conformance to the keep authority.** No hand-written expected answers, so the census cannot rot, and it directly asserts the invariant the four bugs violated.

**Cells are DERIVED from the reason registry**, not hand-picked. For each `KeepReason` × each cap it feeds, generate two cells and drive the **real `StrategyArbiter`** (never a mocked planner):

* **SAFETY cell** — `held == keep`: the plan must **not** dispose that code.
* **LIVENESS cell** — `held > keep` under bag pressure: the plan **must** dispose the surplus.

Plus:
* **Route cells** — each disposal route × available/unavailable (recycle needs workshop+skill+recipe; deposit needs bank; sell needs an NPC buyer).
* **Pressure cells** — slot-full **vs** quantity-full, held separately. This is the dimension the HTTP 497 livelock lived in (`68/124` quantity while `20/20` slots).

### CI gates (`--check` exits non-zero)

1. **`inventory_bug == 0`** — any FAIL not attributable to an honest gap class. Mirrors `planner_bug`: `inventory_bug` means *unexplained*, never *expected*.
2. **Reason coverage** — every `KeepReason` member has ≥1 SAFETY **and** ≥1 LIVENESS cell. **This is the anti-rot mechanism**: adding a protection reason without proving its surplus is still disposable breaks the build. It is the structural guarantee that a fifth instance cannot be introduced silently.

### Honest gap classes

A FAIL is only *not* a bug if it carries a distinct, non-planner reason. The discipline is the craft census's: `inventory_bug` means **unexplained**, never *expected*.

| Class | Meaning |
|---|---|
| `NO_ROUTE_AVAILABLE` | Surplus exists but no route can fire this cycle: not recyclable (no recipe/skill/workshop), no NPC buyer, bank unreachable, and `disposal_route` declines DELETE because the item has future value. Legitimately un-sheddable now. |
| `BANK_FULL` | Bank at capacity, so DEPOSIT cannot take it (tracked separately by the bank-full cascade). |
| `VENUE_UNREACHABLE` | Bank / workshop / NPC exists but no walkable path to it from the cell's position. |
| `KEEP_ALL_SENTINEL` | `CURRENCY` (`tasks_coin`) — never disposable **by design**. Generates a SAFETY cell only; it is the one reason exempt from the LIVENESS requirement, and that exemption is declared here rather than discovered. |
| `INVENTORY_BUG` | Everything else. **Must be 0.** |

`KEEP_ALL_SENTINEL` is the sole exemption from the reason-coverage gate's liveness half; every other `KeepReason` must prove its surplus is disposable.

**All four known instances are LIVENESS cells that fail today** — including the live deposit one. The census is expected to land RED.

---

## 5. Formal lockstep

The cores are Lean-mirrored and move with each phase (Lean + differential + mutation, `formal/gate.sh` green per phase):

`Formal/InventoryCaps.lean`, `Formal/BankSelection.lean`, `Formal/AccumulationSell.lean`, `Formal/DisposalRoute.lean`, `Formal/InventoryProfile.lean`, plus `Contracts.lean` / `Manifest.lean` pins.

The two caps get proved role theorems mirroring the design invariants:

* `bankable ≥ 0` and `bag - bankable = keep_in_bag` (nothing needed in the bag is ever banked);
* `destroyable ≥ 0` and `total - destroyable = keep_owned` (nothing needed is ever destroyed);
* **`keep_owned` protection is never weaker than the destructive routes require** — the property that makes "never delete what banking would have saved" structural.

Mutation anchors are refreshed for every edited line (a rotted anchor reports as a *stale survivor*, as it did in `cd0e6d04`).

---

## 6. Phasing

Deliberately **census-before-migration**: TDD at epic scale, and what the craft census did — it exposed a real architectural bug rather than confirming assumptions.

* **P1 — Authority.** `keep_in_bag` / `keep_owned` pure cores + `KeepReason` registry. Lean-mirrored. **Inert** (no consumer migrated), so it ships safely.
* **P2 — Census.** Harness + `--check` CI gate + gap classes. Lands **RED**: proves the live deposit hoard and any reason-coverage gaps. *The census defines done.*
* **P3 — Migrate consumers**, one at a time, each turning cells green. **Deposit first** — it is the live bug (instance 4). Then recycle, sell, discard.
* **P4 — Retire the legacy surface.** Delete the set-based protection helpers and the `frozenset[str]` params. Census green, `inventory_bug` 0, reason coverage complete, `gate.sh` ALL PARTS PASSED.

Each phase is independently green (suite 100%, gate green) and independently revertible.

---

## 7. Non-goals

* Not re-tuning the pressure thresholds (`DEPOSIT_FULL_FRACTION = 0.90`, etc.). The 0.85-vs-0.90 idling observed on Robby is a *consequence* of the hoard being invisible; re-evaluate only if the census still shows an idling gap once surplus is actually disposable.
* Not changing `disposal_route`'s ordering.
* Not touching acquisition logic (`target_gear` etc. survive in their acquisition role).
