# AI Formal Verification — Phase 1 (Inventory/Economy) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three TLA+/PlusPy specs to the existing `formal/` harness that prove the correctness of the inventory/economy pure-logic components — `task_batch.task_batch_size`, `inventory_caps.useful_quantity_cap`/`overstocked_items`, and `bank_selection.select_bank_deposits` — each against an independent oracle over a bounded, exhaustively enumerated input domain.

**Architecture:** Same harness and technique as the four already-verified specs. Each `.tla` `EXTENDS TLC` (+ Integers/Sequences/FiniteSets as needed), bakes a bounded input domain into a definition, walks a cursor over it in `Next`, and asserts the property per input via `TLC!Assert(cond, msg)` against an independent oracle (clamp recomputation / hand table / fixpoint). Specs are registered in `formal/run.py` and mapped in `formal/README.md`.

**Tech Stack:** TLA+ (PlusPy subset), PlusPy (already vendored at `formal/vendor/PlusPy`), Python 3.13 stdlib runner.

---

## Critical environment facts (apply to every task)

- PlusPy entry: `python3 formal/vendor/PlusPy/pluspy.py`. If `formal/vendor/` is missing, run `./formal/setup.sh` first.
- Manual run for module `M` with domain size `N`:
  `python3 formal/vendor/PlusPy/pluspy.py -c<N> -P formal/specs:formal/vendor/PlusPy/modules/lib <M>`
- CLEAN run prints `MAIN DONE` and exits 0. A FAILED `Assert` prints `Evaluating Assert (...) failed` + `AssertionError: <msg>` and exits 1.
- Runner: `python3 formal/run.py` (NOT `uv run` inside a worktree without the editable client; the runner is pure stdlib). Add modules by appending `(name, domain_size)` to its `MODULES` list.
- **PlusPy has NO `RECURSIVE` operator keyword.** Use recursive *functions* `f[k \in S] == ...` over a bounded domain (e.g. `Sat[k \in 0..N, r \in Items]` for closures). PlusPy supports `ASSUME`, records `[a |-> 1]`, functions `[x \in S |-> e]`, set comprehensions, `UNION`, `SUBSET`, `\X`, `DOMAIN`, `Cardinality` (EXTENDS FiniteSets), `\div`, `Len`/`Append`/`\o` (EXTENDS Sequences), `\E`/`\A`, `LET`/`IF`.
- The intended `.tla` in each task is the **contract**; adapt surface syntax to PlusPy's subset if it rejects a construct (consult `formal/vendor/PlusPy/modules/*.tla`), but do NOT drop or weaken any asserted property. If a property genuinely cannot be expressed after real effort, report BLOCKED with specifics — never fake a pass.
- Reuse the enumeration idiom: `VARIABLE todo`; `Init == todo = <domain set>`; `Next == /\ todo # {} /\ \E x \in todo : /\ Assert(Correct(x), <<"<M> FAIL", x>>) /\ todo' = todo \ {x}`; run with `-c|domain|`.

## File structure

- Create `formal/specs/TaskBatch.tla`
- Create `formal/specs/InventoryCaps.tla`
- Create `formal/specs/BankSelection.tla`
- Modify `formal/run.py` (append three `MODULES` entries)
- Modify `formal/README.md` (append three property→code rows)

---

## Task 1: TaskBatch — clamp bounds for `task_batch_size`

Mirrors `src/artifactsmmo_cli/ai/task_batch.py:19`. The `recipe_closure`/`raw_material_units` math is already proven (`RecipeClosure.tla`), so this spec abstracts `mats_per_unit` and `held_recipe` as enumerated inputs and verifies the NEW logic: the clamp `max(1, min(remaining, fit, BATCH_CAP))` and its bound guarantees.

**Files:** Create `formal/specs/TaskBatch.tla`; Modify `formal/run.py`.

- [ ] **Step 1: Write `formal/specs/TaskBatch.tla`**

```tla
-------------------------------- MODULE TaskBatch --------------------------------
EXTENDS Integers, TLC

\* Constants mirror task_batch.py.
BatchCap == 10        \* BATCH_CAP
MinFree  == 3         \* _MIN_FREE_SLOTS

Max(a, b) == IF a > b THEN a ELSE b
Min(a, b) == IF a < b THEN a ELSE b

\* Bounded input domain. items_task=FALSE folds in the "not an items task / no
\* code / total<=0" early-return; the numeric fields cover remaining<=0, the
\* negative-usable floor, and each of remaining/fit/cap being the binding min.
Bool   == {TRUE, FALSE}
Totals == 0..4        \* task_total
Progs  == 0..4        \* task_progress
Frees  == 0..6        \* inventory_free
Helds  == 0..4        \* held_recipe (sum of held closure resources)
Mats   == 1..3        \* mats_per_unit = raw_material_units(task_code) (>=1)

Cases == { [it |-> it, tot |-> tot, prog |-> prog, free |-> free, held |-> held, mats |-> mats] :
             it \in Bool, tot \in Totals, prog \in Progs,
             free \in Frees, held \in Helds, mats \in Mats }

\* ---- algorithm model: task_batch_size ----
FloorDiv(a, b) == IF a < 0 THEN -(((-a) + b - 1) \div b) ELSE a \div b  \* floor div matching Python //
BatchSize(c) ==
  IF ~c.it \/ c.tot <= 0 THEN 1
  ELSE LET remaining == c.tot - c.prog IN
       IF remaining <= 0 THEN 1
       ELSE LET usable == (c.free + c.held) - MinFree
                fit    == FloorDiv(usable, c.mats)
            IN Max(1, Min(Min(remaining, fit), BatchCap))

\* ---- independent oracle: bound invariants (do NOT reuse BatchSize's formula) ----
Correct(c) ==
  LET k == BatchSize(c)
      remaining == c.tot - c.prog
      taskBranch == c.it /\ c.tot > 0 /\ remaining > 0
      usable == (c.free + c.held) - MinFree
  IN /\ k >= 1                                  \* floor always holds
     /\ (~taskBranch => k = 1)                  \* early-returns yield 1
     /\ (taskBranch =>
            /\ k <= remaining                   \* never overshoot the task
            /\ k <= BatchCap                     \* respect the depth cap
            /\ (usable >= c.mats => k * c.mats <= usable)  \* a >=1 batch fits the space
            /\ (usable < c.mats => k = 1))       \* no room => floor to 1

VARIABLE todo
Init == todo = Cases
Next == /\ todo # {}
        /\ \E c \in todo :
              /\ Assert(Correct(c), <<"TaskBatch FAIL", c>>)
              /\ todo' = todo \ {c}
================================================================================
```

- [ ] **Step 2: Compute domain size and run**

|Cases| = 2·5·5·7·5·3 = **5250**.
Run: `python3 formal/vendor/PlusPy/pluspy.py -c5250 -P formal/specs:formal/vendor/PlusPy/modules/lib TaskBatch`
Expected: `MAIN DONE`, exit 0. If PlusPy is too slow at 5250, reduce the ranges (e.g. `Totals == 0..3`, `Progs == 0..3`, `Frees == 0..5`, `Helds == 0..3`, `Mats == 1..2`) AND recompute the iteration count to the new `|Cases|`, keeping at least: an `it=FALSE` case, a `remaining<=0` case, a `usable<mats` (negative/small) case, and cases where each of remaining/fit/cap binds. Document any reduction in a `\*` comment.

- [ ] **Step 3: Sanity-bite (prove non-vacuous)**

Temporarily change `BatchSize`'s final line to `Max(1, Min(remaining, fit))` (drop the `BatchCap` clamp). Run the same command; expect a halt with `<<"TaskBatch FAIL", ...>>` on a case where `min(remaining,fit) > 10`. Then REVERT. (If your reduced domain can't exceed BatchCap, instead break the floor: change `Max(1, ...)` to `Min(remaining, ...)` without the `1` floor and confirm a `usable<mats` case fails.)

- [ ] **Step 4: Register in the runner**

In `formal/run.py`, append to `MODULES`: `("TaskBatch", 5250)` (or your reduced count).

- [ ] **Step 5: Run the runner**

Run: `python3 formal/run.py`
Expected: all modules incl. `TaskBatch  PASS`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add formal/specs/TaskBatch.tla formal/run.py
git commit -m "test(formal): TaskBatch clamp-bounds spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: InventoryCaps — `useful_quantity_cap` + `overstocked_items`

Mirrors `src/artifactsmmo_cli/ai/inventory_caps.py:30,82`. Item attributes (max recipe demand, equippability, action-consumable cap) and state (task item + remaining, equipped set) are modeled as small tables; the spec verifies the cap formula and the overstock derivation.

**Files:** Create `formal/specs/InventoryCaps.tla`; Modify `formal/run.py`.

- [ ] **Step 1: Write `formal/specs/InventoryCaps.tla`**

```tla
------------------------------- MODULE InventoryCaps -------------------------------
EXTENDS Integers, FiniteSets, TLC

BatchBuffer == 5      \* BATCH_BUFFER
SafetyFloor == 3      \* SAFETY_FLOOR
EquipKeep   == 1      \* EQUIPPABLE_KEEP
CoinCap     == 9      \* ACTION_CONSUMABLES_CAP[tasks_coin]

Max(a, b) == IF a > b THEN a ELSE b

\* Item universe with attributes (mirrors GameData getters).
Items == {"coin", "ore", "sword", "potion", "junk"}
\* max_recipe_demand(code): the largest qty any recipe needs of code (0 if none).
RecipeDemand == [ coin |-> 0, ore |-> 6, sword |-> 0, potion |-> 0, junk |-> 0 ]
\* equippable: ITEM_TYPE_TO_SLOTS maps the item's type to >=1 slot.
Equippable   == [ coin |-> FALSE, ore |-> FALSE, sword |-> TRUE, potion |-> FALSE, junk |-> FALSE ]
\* action-consumable cap (only tasks_coin here).
ActionCap    == [ coin |-> CoinCap, ore |-> 0, sword |-> 0, potion |-> 0, junk |-> 0 ]
TasksCoin == "coin"

\* ---- per-item cap (algorithm model) ----
RecipeCap(code) ==
  LET rmax == RecipeDemand[code] IN
  IF rmax > 0 THEN Max(rmax * BatchBuffer, SafetyFloor) ELSE 0

\* state: which item is the active items-task target and its remaining count,
\* plus the set of equipped item codes.
CapExclEquipped(code, taskItem, remaining) ==
  LET recipe_cap == RecipeCap(code)
      task_cap   == IF code = taskItem THEN remaining ELSE 0
      action_cap == ActionCap[code]
      equip_cap  == IF Equippable[code] THEN EquipKeep ELSE 0
  IN Max(Max(recipe_cap, task_cap), Max(action_cap, equip_cap))

Cap(code, taskItem, remaining, equipped) ==
  IF code \in equipped
  THEN Max(1, CapExclEquipped(code, taskItem, remaining))
  ELSE CapExclEquipped(code, taskItem, remaining)

\* ---- independent oracle for the cap: recompute max-of-four + equipped floor,
\* and assert the equipped invariant directly ----
OracleCap(code, taskItem, remaining, equipped) ==
  LET base == IF RecipeDemand[code] > 0 THEN Max(RecipeDemand[code] * BatchBuffer, SafetyFloor) ELSE 0
      t    == IF code = taskItem THEN remaining ELSE 0
      a    == ActionCap[code]
      e    == IF Equippable[code] THEN EquipKeep ELSE 0
      m    == Max(Max(base, t), Max(a, e))
  IN IF code \in equipped THEN Max(1, m) ELSE m

\* enumerate cap correctness over item x taskItem x remaining x equipped-subset
TaskItems == Items \cup {"none"}
Remains   == 0..3
EquipSets == SUBSET {"sword", "ore"}   \* the plausibly-equipped codes

CapCases == { [code |-> code, ti |-> ti, rem |-> rem, eq |-> eq] :
                code \in Items, ti \in TaskItems, rem \in Remains, eq \in EquipSets }

CapCorrect(c) ==
  /\ Cap(c.code, c.ti, c.rem, c.eq) = OracleCap(c.code, c.ti, c.rem, c.eq)
  /\ (c.code \in c.eq => Cap(c.code, c.ti, c.rem, c.eq) >= 1)

\* ---- overstock over a few hand inventories (independent expected dicts) ----
\* Inventory as a function code->qty over a subset; cap computed per code.
\* Overstock(code) = qty - cap when qty>0 and qty>cap.
Overstock(inv, taskItem, remaining, equipped) ==
  [ code \in { c \in DOMAIN inv : inv[c] > 0 /\ inv[c] > Cap(c, taskItem, remaining, equipped) }
        |-> inv[code] - Cap(code, taskItem, remaining, equipped) ]

\* Hand cases: (inventory, taskItem, remaining, equipped, expected-overstock).
\* ore cap = max(6*5,3)=30; sword cap (equippable,not equipped)=1, (equipped)=>>=1;
\* potion/junk cap=0; coin cap=9.
OverCases == {
  [inv |-> [ore |-> 40, junk |-> 2, coin |-> 12], ti |-> "none", rem |-> 0, eq |-> {},
   exp |-> [ore |-> 10, junk |-> 2, coin |-> 3]],
  [inv |-> [sword |-> 3], ti |-> "none", rem |-> 0, eq |-> {},
   exp |-> [sword |-> 2]],                                   \* cap 1, excess 2
  [inv |-> [sword |-> 3], ti |-> "none", rem |-> 0, eq |-> {"sword"},
   exp |-> [sword |-> 2]],                                   \* equipped floor 1, still excess 2
  [inv |-> [ore |-> 5], ti |-> "none", rem |-> 0, eq |-> {},
   exp |-> << >>]                                            \* 5 <= cap 30, no overstock
}

OverCorrect(c) == Overstock(c.inv, c.ti, c.rem, c.eq) = c.exp

\* Two enumerated families share one Next via a tagged union.
Tagged == { [kind |-> "cap", v |-> c] : c \in CapCases }
            \cup { [kind |-> "over", v |-> c] : c \in OverCases }
CheckTagged(t) == IF t.kind = "cap" THEN CapCorrect(t.v) ELSE OverCorrect(t.v)

VARIABLE todo
Init == todo = Tagged
Next == /\ todo # {}
        /\ \E t \in todo :
              /\ Assert(CheckTagged(t), <<"InventoryCaps FAIL", t>>)
              /\ todo' = todo \ {t}
================================================================================
```

- [ ] **Step 2: Compute domain size and run**

|CapCases| = 5·6·4·|SUBSET {sword,ore}| = 5·6·4·4 = 480. |OverCases| = 4. |Tagged| = **484**.
Run: `python3 formal/vendor/PlusPy/pluspy.py -c484 -P formal/specs:formal/vendor/PlusPy/modules/lib InventoryCaps`
Expected: `MAIN DONE`, exit 0. Adapt syntax to PlusPy's subset if needed (the `[code \in {...} |-> ...]` set-builder function and record-of-records are the riskiest constructs — if PlusPy rejects them, represent `inv`/`exp` as functions built with `[c \in S |-> v]` and compare with `=`; verify the empty-overstock case uses an empty function `[c \in {} |-> 0]`).

- [ ] **Step 3: Sanity-bite (prove non-vacuous)**

Temporarily change `RecipeCap` to drop the safety floor (`IF rmax > 0 THEN rmax * BatchBuffer ELSE 0`) — this does not change these cases (30 either way), so instead break the equipped floor: change `Cap` to return `CapExclEquipped(...)` unconditionally (no `Max(1, ...)`). With `equipped` containing a 0-cap item (add `[code |-> "junk", ti |-> "none", rem |-> 0, eq |-> {"junk"}]`-style coverage already in CapCases via `eq` subsets? `eq` only has sword/ore) — to guarantee a bite, temporarily change `OverCases`' first `exp` `ore |-> 10` to `ore |-> 9` and confirm `Evaluating Assert ... failed` on the `over` case. REVERT.

- [ ] **Step 4: Register in the runner**

In `formal/run.py`, append: `("InventoryCaps", 484)` (adjust if you changed the domain).

- [ ] **Step 5: Run the runner**

Run: `python3 formal/run.py` — expect all PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add formal/specs/InventoryCaps.tla formal/run.py
git commit -m "test(formal): InventoryCaps cap + overstock spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: BankSelection — keep-set closure + deposit filter/sort

Mirrors `src/artifactsmmo_cli/ai/bank_selection.py:68` (`select_bank_deposits`, `_keep_codes`, `_recipe_materials`, `_best_fighting_weapon`). This is the highest-value spec: the keep-set closure is the documented PursueTask-freeze root cause. Verified over a small set of hand-built states (including one where a recipe material is the items-task item).

**Files:** Create `formal/specs/BankSelection.tla`; Modify `formal/run.py`.

- [ ] **Step 1: Write `formal/specs/BankSelection.tla`**

```tla
------------------------------- MODULE BankSelection -------------------------------
EXTENDS Integers, FiniteSets, Sequences, TLC

TasksCoin == "coin"

\* Item universe + attributes (mirrors GameData getters).
Items == {"coin", "iron", "wood", "blade", "sword", "potion", "axe", "stick"}
\* recipe[code] = set of immediate material codes (empty if not craftable).
Recipe == [ coin  |-> {}, iron |-> {}, wood |-> {}, potion |-> {}, stick |-> {},
            blade |-> {"iron"},
            sword |-> {"blade", "stick"},
            axe   |-> {"wood"} ]
HpRestore == [ coin |-> 0, iron |-> 0, wood |-> 0, blade |-> 0, sword |-> 0,
               potion |-> 40, axe |-> 0, stick |-> 0 ]
IsWeapon  == [ coin |-> FALSE, iron |-> FALSE, wood |-> FALSE, blade |-> FALSE,
               sword |-> TRUE, potion |-> FALSE, axe |-> TRUE, stick |-> FALSE ]
\* tools have skill_effects -> excluded from "fighting weapon"
IsTool    == [ coin |-> FALSE, iron |-> FALSE, wood |-> FALSE, blade |-> FALSE,
               sword |-> FALSE, potion |-> FALSE, axe |-> TRUE, stick |-> FALSE ]
Attack    == [ coin |-> 0, iron |-> 0, wood |-> 0, blade |-> 0, sword |-> 10,
               potion |-> 0, axe |-> 8, stick |-> 0 ]
SellValue == [ coin |-> 0, iron |-> 5, wood |-> 3, blade |-> 12, sword |-> 50,
               potion |-> 7, axe |-> 20, stick |-> 1 ]

\* ---- recipe-material closure (visited-guarded walk; bounded recursive fn) ----
N == Cardinality(Items)
ExpandMats(S) == S \cup UNION { Recipe[m] : m \in S }
\* Sat[k, r]: materials reachable from root r within k expansion rounds.
\* Materials of a root EXCLUDE the root itself (walk adds recipe members only).
Sat[k \in 0..N, r \in Items] == IF k = 0 THEN Recipe[r] ELSE ExpandMats(Sat[k-1, r])
MatsOf(r) == Sat[N, r]
MatsOfRoots(roots) == UNION { MatsOf(r) : r \in roots }

\* ---- best fighting weapon: max Attack over non-tool weapons in inv+equipped,
\* ties by code asc; "none" if none ----
WeaponCands(inv, equipped) == { c \in (DOMAIN inv \cup equipped) : IsWeapon[c] /\ ~IsTool[c] }
BestWeapon(inv, equipped) ==
  LET cands == WeaponCands(inv, equipped) IN
  IF cands = {} THEN "none"
  ELSE CHOOSE w \in cands :
         \A o \in cands : (Attack[w] > Attack[o]) \/ (Attack[w] = Attack[o] /\ w <= o)

\* ---- keep-set (algorithm model) ----
\* state record: inv (code->qty), equipped (set), taskCode (or "none"),
\* taskType ("items" or "other"), craftingTarget (or "none").
KeepSet(s) ==
  LET base == {TasksCoin}
      withTask == IF s.taskCode # "none" THEN base \cup {s.taskCode} ELSE base
      hp == { c \in DOMAIN s.inv : HpRestore[c] > 0 }
      bw == BestWeapon(s.inv, s.equipped)
      withWeapon == (withTask \cup hp) \cup (IF bw # "none" THEN {bw} ELSE {})
      roots == (IF s.craftingTarget # "none" THEN {s.craftingTarget} ELSE {})
                 \cup (IF s.taskType = "items" /\ s.taskCode # "none" THEN {s.taskCode} ELSE {})
  IN withWeapon \cup MatsOfRoots(roots)

\* ---- deposits: inv codes with qty>0 not in keep, sorted (-SellValue, code) ----
DepositSet(s) == { c \in DOMAIN s.inv : s.inv[c] > 0 /\ c \notin KeepSet(s) }

\* sort key non-decreasing check over the produced sequence (built by the model
\* the same way Python sorts: by (-SellValue, code)). We verify the SET is right
\* and that an ordering exists respecting the key; PlusPy can't call list.sort,
\* so assert: DepositSet equals the model set AND for the canonical sorted
\* sequence the key is non-decreasing. Build the sorted seq by selection.
RECURSIVE_NOTE == "no RECURSIVE kw; build SortedSeq via a bounded recursive fn over the set size"
Key(c) == << -SellValue[c], c >>   \* lexicographic; PlusPy compares tuples
\* SortedSeq[k, S]: pull the Key-minimum element k times. Implement as recursive fn.
Pull(S) == CHOOSE m \in S : \A o \in S : Key(m) \o <<>> = Key(m) /\ LE(Key(m), Key(o))
\* (LE = lexicographic <= on <<int,str>>; define explicitly)
LE(a, b) == (a[1] < b[1]) \/ (a[1] = b[1] /\ a[2] <= b[2])

\* ---- properties ----
\* Hand states; the THIRD has a recipe material (iron) that is ALSO the items-task
\* item -> exercises the freeze guard: iron must be kept, not deposited.
States == {
  [inv |-> [iron |-> 9, wood |-> 4, potion |-> 2, sword |-> 1],
   equipped |-> {"sword"}, taskCode |-> "coin", taskType |-> "other",
   craftingTarget |-> "sword"],
  [inv |-> [iron |-> 3, blade |-> 1, axe |-> 1, stick |-> 2],
   equipped |-> {}, taskCode |-> "none", taskType |-> "other",
   craftingTarget |-> "none"],
  [inv |-> [iron |-> 5, wood |-> 2, potion |-> 1],
   equipped |-> {}, taskCode |-> "iron", taskType |-> "items",
   craftingTarget |-> "none"]
}

\* Expected keep-set per state (hand-computed, independent of KeepSet):
\*  s1: coin + taskCode(coin) + hp(potion) + bestweapon(sword) + mats(sword)={blade,stick,iron}
\*      = {coin, potion, sword, blade, stick, iron}
\*  s2: coin + hp() + bestweapon(non-tool weapons: none; axe is a tool) -> none
\*      + mats() = {coin}
\*  s3: coin + taskCode(iron) + hp(potion) + bestweapon(none) + mats(iron)={}  (iron raw)
\*      = {coin, iron, potion}   -> iron kept (freeze guard), so NOT deposited
ExpectedKeep == [
  s1 |-> {"coin", "potion", "sword", "blade", "stick", "iron"},
  s2 |-> {"coin"},
  s3 |-> {"coin", "iron", "potion"} ]
\* tag states for lookup
TagOf(s) == IF s.craftingTarget = "sword" THEN "s1"
            ELSE IF s.taskCode = "iron" THEN "s3" ELSE "s2"

Correct(s) ==
  LET keep == KeepSet(s)
      dep  == DepositSet(s)
  IN /\ keep = ExpectedKeep[TagOf(s)]          \* keep-set matches the hand oracle
     /\ dep \cap keep = {}                       \* FREEZE INVARIANT: never bank a kept item
     /\ dep = { c \in DOMAIN s.inv : s.inv[c] > 0 /\ c \notin keep }  \* exact filter
     /\ MatsOfRoots(IF s.taskType = "items" /\ s.taskCode # "none"
                    THEN {s.taskCode} ELSE {}) \subseteq keep         \* task inputs protected

VARIABLE todo
Init == todo = States
Next == /\ todo # {}
        /\ \E s \in todo :
              /\ Assert(Correct(s), <<"BankSelection FAIL", TagOf(s)>>)
              /\ todo' = todo \ {s}
================================================================================
```

> **Implementer note:** the `Pull`/`SortedSeq`/`RECURSIVE_NOTE` sketch above is a hint, not required syntax. PlusPy cannot call `list.sort`, so verify the **sort key is well-defined and the deposit SET is exact** (the `dep = {...}` and `LE` machinery). If proving "a non-decreasing sorted ordering exists" is awkward in PlusPy, it is sufficient to assert: (a) the deposit set is exact, (b) `dep ∩ keep = {}`, (c) `Key` is a total order on `dep` (antisymmetry/totality via `LE`), and drop the explicit `SortedSeq`. The Python `.sort` is the stdlib's correctness, not ours — what matters is the key and the set. Remove the `Pull`/`RECURSIVE_NOTE` lines if unused. Preserve the four `Correct` conjuncts (keep-oracle match, freeze invariant, exact filter, task-input protection).

- [ ] **Step 2: Run (domain size = |States| = 3)**

Run: `python3 formal/vendor/PlusPy/pluspy.py -c3 -P formal/specs:formal/vendor/PlusPy/modules/lib BankSelection`
Expected: `MAIN DONE`, exit 0. Iterate on PlusPy-subset syntax (records-of-functions and the `Sat[k,r]` closure are the riskiest) until clean. Verify by hand that `ExpectedKeep` is correct for the recipe data before trusting it; correct it if your trace differs (and note the correction).

- [ ] **Step 3: Sanity-bite (prove the freeze invariant bites)**

Temporarily remove the task-input protection from `KeepSet` (delete the `\cup MatsOfRoots(roots)` term, or the `taskType="items"` root). On state `s3`, `iron` (the items-task item) is raw so its mats are empty — instead, to exercise the closure guard, change `s3.taskCode` handling: temporarily drop `s.taskCode` from `withTask`. Then `iron` leaves the keep-set, `dep ∩ keep = {}` still holds but `keep = ExpectedKeep` fails and the task-input/`taskCode` protection fails. Confirm `Evaluating Assert ... failed` for `s3`. REVERT. (Also confirm: temporarily change `ExpectedKeep.s1` to drop `"iron"` → fails, proving the recipe-material closure is actually exercised on s1 where `sword`→`blade`→`iron`.)

- [ ] **Step 4: Register in the runner**

In `formal/run.py`, append: `("BankSelection", 3)`.

- [ ] **Step 5: Run the runner**

Run: `python3 formal/run.py` — expect all modules PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add formal/specs/BankSelection.tla formal/run.py
git commit -m "test(formal): BankSelection keep-set closure + deposit spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: README — Phase 1 property→code map

**Files:** Modify `formal/README.md`.

- [ ] **Step 1: Append three rows to the property→code table in `formal/README.md`**

Add these rows to the existing `## Property -> code map` table (match the existing column format):

```markdown
| `TaskBatch.tla` | `ai/task_batch.py:19` | `task_batch_size` clamps to `max(1, min(remaining, fit, BATCH_CAP))`: always >=1, never exceeds the task remainder or the depth cap, and a >=1 batch always fits the available inventory space (`K*mats <= free+held-MIN_FREE`). |
| `InventoryCaps.tla` | `ai/inventory_caps.py:30,82` | `useful_quantity_cap` = max(recipe_demand*buffer floored at safety, task_remaining, action_cap, equip_keep) with equipped => >=1; `overstocked_items` = `{code: qty-cap : qty>cap}` exactly. |
| `BankSelection.tla` | `ai/bank_selection.py:68` | `select_bank_deposits` deposits exactly the non-kept positive-qty inventory; the keep-set is closed under the recipe-material walk of {crafting_target, items-task item} plus task-coin/HP/best-weapon, so deposits never intersect the keep-set (the PursueTask-freeze invariant); sort key is the total order (-sell_value, code). |
```

- [ ] **Step 2: Add a Phase-1 note under Modeling notes in `formal/README.md`**

Append to the `## Modeling notes` section:

```markdown
- The inventory/economy specs (`TaskBatch`, `InventoryCaps`, `BankSelection`)
  abstract item attributes (recipe demand, sell value, equippability, HP-restore)
  as small in-spec tables and reuse the recipe-material closure already proven in
  `RecipeClosure.tla`. `TaskBatch` abstracts `raw_material_units`/`recipe_closure`
  (proven separately) as the enumerated `mats_per_unit`/`held_recipe` inputs and
  verifies only the clamp it adds.
```

- [ ] **Step 3: Final full run**

Run: `python3 formal/run.py`
Expected: every module PASS (Smoke, CalculatePath, RecipeClosure, PrerequisiteGraph, PredictWin, TaskBatch, InventoryCaps, BankSelection), exit 0.

- [ ] **Step 4: Commit**

```bash
git add formal/README.md
git commit -m "docs(formal): map Phase 1 inventory/economy specs to code

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review notes (addressed)

- **Spec coverage:** Phase-1 spec's three components each get a task (1–3); README map task (4). Phases 2–4 are explicitly out of this plan.
- **Independent oracles:** TaskBatch = bound invariants (not the clamp formula); InventoryCaps = max-of-four recompute + hand overstock table; BankSelection = hand keep-set table + freeze invariant + exact-filter + task-input-subset. Each task has a "sanity-bite" step proving non-vacuity.
- **Reuse:** TaskBatch abstracts the already-proven `raw_material_units`; BankSelection reuses the `Recipeclosure`-style `Sat[k,r]` closure idiom. No re-proving of closure math.
- **PlusPy reality:** no `RECURSIVE` keyword (use `Sat[k,r]`), enumerate-and-`Assert`, combined `-P` path, `MAIN DONE`/exit-0 success — all consistent with the four existing specs.
- **No placeholders:** the only intentional fill-ins are PlusPy-subset syntax adaptation and domain-size tuning, each with explicit guidance; the `Pull`/`RECURSIVE_NOTE` sketch in Task 3 is flagged as removable with a concrete fallback (assert set-exactness + total-order, drop explicit sort sequence).
- **Type/name consistency:** module names and `MODULES` counts (5250/484/3) are consistent across tasks and the runner; constant names mirror the Python (`BATCH_CAP`/`_MIN_FREE_SLOTS`/`BATCH_BUFFER`/`SAFETY_FLOOR`/`EQUIPPABLE_KEEP`).
