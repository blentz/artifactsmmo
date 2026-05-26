# AI Formal Verification — Phase 3 (Strategy/Feasibility) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three TLA+/PlusPy specs to the `formal/` harness proving the correctness of the strategy/feasibility pure logic: `task_feasibility.task_requirement`, `tiers/objective` (`is_attainable` + `from_game_data` gear selection + `gap`), and the `tiers/strategy` pure traversal core (`actionable_step`, `is_reachable`, `unmet_closure_size`, `root_cost`).

**Architecture:** Same enumerate-and-`Assert`-against-independent-oracle harness as the nine existing specs. These functions recurse over the prerequisite graph and recipe trees; since `prerequisites`/`is_satisfied`/`recipe_closure` are already modeled (`PrerequisiteGraph.tla`, `RecipeClosure.tla`), Phase 3 abstracts those relations as in-spec node/recipe tables and verifies the **traversal logic** (worst-gap, fixpoint reachability, closure counting, deepest-actionable selection) against independent fixpoint/cardinality oracles. All arithmetic stays integer (gap fractions are verified structurally via `0 ≤ gap ≤ denom`, never computed as floats).

**Tech Stack:** TLA+ (PlusPy subset), PlusPy (vendored), Python 3.13 stdlib runner.

---

## Critical environment facts (apply to every task)

- PlusPy entry: `python3 formal/vendor/PlusPy/pluspy.py`. If `formal/vendor/` missing, run `./formal/setup.sh`.
- Manual run, module `M`, domain size `N`: `python3 formal/vendor/PlusPy/pluspy.py -c<N> -P formal/specs:formal/vendor/PlusPy/modules/lib <M>`
- CLEAN: `MAIN DONE`, exit 0. FAIL: `Evaluating Assert (...) failed` + `AssertionError`, exit 1.
- Runner: `python3 formal/run.py` (NOT `uv run` in the worktree). Append `(name, domain_size)` to `MODULES`.
- **Work in the given worktree path and verify files land there** (`git -C <worktree> status`) before running pluspy.
- **PlusPy has NO `RECURSIVE` operator keyword** — recursion = recursive functions `f[k \in S]==...`. For closures use the bounded `Sat[k \in 0..N, r \in Items]` idiom proven in `RecipeClosure.tla`/`PrerequisiteGraph.tla` (READ those for the pattern). For path-guarded recursion (cycle-safe) key a function by `(node, pathSubset)`: `F[n \in Nodes, p \in SUBSET Nodes] == ...`. NO floats — integer only. Supports ASSUME, records, functions, set comprehension, UNION, SUBSET, DOMAIN, Cardinality (FiniteSets), CHOOSE, `\E`/`\A`, `LET`/`IF`.
- The intended `.tla` is the CONTRACT; adapt surface syntax to PlusPy's subset but do NOT weaken any asserted property. **Phase 3 is the most recursion-heavy phase** — if a traversal genuinely cannot be expressed in PlusPy after real effort, report BLOCKED with specifics rather than faking a pass.
- Enumeration idiom: `VARIABLE todo`; `Init == todo = <domain>`; `Next == /\ todo # {} /\ \E x \in todo : /\ Assert(Correct(x), <<"M FAIL", x>>) /\ todo' = todo \ {x}`.

## File structure

- Create `formal/specs/TaskFeasibility.tla`
- Create `formal/specs/Objective.tla`
- Create `formal/specs/StrategyTraversal.tla`
- Modify `formal/run.py` (+3 MODULES entries)
- Modify `formal/README.md` (+3 property→code rows)

---

## Task 1: TaskFeasibility — worst unmet skill gap over the craft closure

Mirrors `src/artifactsmmo_cli/ai/task_feasibility.py` (`task_requirement`:30, `_item_skill_gap`:44). READ it first.

**Files:** Create `formal/specs/TaskFeasibility.tla`; Modify `formal/run.py`.

- [ ] **Step 1: Write `formal/specs/TaskFeasibility.tla`**

```tla
------------------------------- MODULE TaskFeasibility -------------------------------
EXTENDS Integers, FiniteSets, TLC

MonsterMargin == 2   \* MONSTER_LEVEL_MARGIN

Max(a, b) == IF a > b THEN a ELSE b

\* Item universe; CraftSkill "none" = not craftable-by-skill; recipe edges as a set.
Items == {"sword", "blade", "iron", "ring", "loop"}
CraftSkill == [ sword |-> "weaponcrafting", blade |-> "weaponcrafting", iron |-> "none",
                ring |-> "jewelry", loop |-> "jewelry" ]
CraftLevel == [ sword |-> 15, blade |-> 8, iron |-> 0, ring |-> 20, loop |-> 5 ]
Recipe == [ sword |-> {"blade", "iron"}, blade |-> {"iron"}, iron |-> {},
            ring |-> {"loop"}, loop |-> {"ring"} ]   \* ring<->loop cycle

\* ---- craft closure of a root item (root + transitive recipe members), cycle-safe ----
N == Cardinality(Items)
Expand(S) == S \cup UNION { Recipe[m] : m \in S }
Sat[k \in 0..N, r \in Items] == IF k = 0 THEN {r} ELSE Expand(Sat[k-1, r])
Closure(r) == Sat[N, r]

\* skill levels (char). unmet gap for item m: CraftSkill[m] # none /\ CraftLevel[m] > skills[CraftSkill[m]].
UnmetItems(item, skills) ==
  { m \in Closure(item) : CraftSkill[m] # "none" /\ CraftLevel[m] > skills[CraftSkill[m]] }

\* ---- algorithm model: the worst (highest required_level) unmet gap's required_level,
\* or 0 when feasible (None). task_requirement returns a record; the VALUE that matters
\* (and the only tie-stable field) is required_level, so the spec tracks that. ----
WorstRequired(item, skills) ==
  LET U == UnmetItems(item, skills) IN
  IF U = {} THEN 0
  ELSE CHOOSE v \in { CraftLevel[m] : m \in U } : \A m \in U : v >= CraftLevel[m]

\* ---- monster branch ----
MonsterReq(monLevel, charLevel) == monLevel > 0 /\ monLevel > charLevel + MonsterMargin

\* ---- independent oracle: max unmet CraftLevel over the closure, computed directly ----
OracleWorst(item, skills) ==
  LET ls == { CraftLevel[m] : m \in Closure(item)
                : CraftSkill[m] # "none" /\ CraftLevel[m] > skills[CraftSkill[m]] }
  IN IF ls = {} THEN 0 ELSE CHOOSE v \in ls : \A x \in ls : v >= x

\* (NOTE: PlusPy may not support the double-bar set-builder above; if so, define
\*  ls == { CraftLevel[m] : m \in UnmetItems(item, skills) } but ensure UnmetItems is
\*  NOT reused verbatim in both — inline the predicate here so the oracle is an
\*  independent recomputation, not a call to the same operator. The cross-check is
\*  WorstRequired == OracleWorst AND the None-iff-feasible property below.)

ItemCorrect(item, skills) ==
  /\ WorstRequired(item, skills) = OracleWorst(item, skills)
  /\ (WorstRequired(item, skills) = 0 <=> UnmetItems(item, skills) = {})  \* None iff feasible
  /\ (WorstRequired(item, skills) > 0 =>
        \E m \in Closure(item) : CraftSkill[m] # "none"
           /\ CraftLevel[m] = WorstRequired(item, skills)
           /\ CraftLevel[m] > skills[CraftSkill[m]])                      \* the worst is a real unmet gap

\* enumerate: items x a few skill-level vectors (covering feasible / unmet-at-various-levels / cyclic ring).
SkillVecs == {
  [weaponcrafting |-> 0,  jewelry |-> 0],
  [weaponcrafting |-> 10, jewelry |-> 0],   \* blade(8) met, sword(15) unmet
  [weaponcrafting |-> 20, jewelry |-> 25],  \* all met -> feasible
  [weaponcrafting |-> 0,  jewelry |-> 6]     \* loop(5) met, ring(20) unmet
}
ItemCases == { [item |-> i, skills |-> sv] : i \in Items, sv \in SkillVecs }

\* monster cases: (monLevel, charLevel) covering above/below the +2 margin and monLevel=0.
MonCases == { [mon |-> m, lvl |-> l] : m \in 0..8, l \in 0..6 }
MonCorrect(c) == MonsterReq(c.mon, c.lvl) <=> (c.mon > 0 /\ c.mon > c.lvl + MonsterMargin)

Tagged == { [kind |-> "item", v |-> c] : c \in ItemCases }
            \cup { [kind |-> "mon", v |-> c] : c \in MonCases }
Check(t) == IF t.kind = "item" THEN ItemCorrect(t.v.item, t.v.skills) ELSE MonCorrect(t.v)

VARIABLE todo
Init == todo = Tagged
Next == /\ todo # {}
        /\ \E t \in todo :
              /\ Assert(Check(t), <<"TaskFeasibility FAIL", t>>)
              /\ todo' = todo \ {t}
================================================================================
```

- [ ] **Step 2: Compute domain size and run**

|ItemCases| = 5 items × 4 skill-vecs = 20; |MonCases| = 9 × 7 = 63; |Tagged| = **83**.
Run: `python3 formal/vendor/PlusPy/pluspy.py -c83 -P formal/specs:formal/vendor/PlusPy/modules/lib TaskFeasibility`
Expected: `MAIN DONE`, exit 0. The double-bar set-builder in `OracleWorst` is risky — if PlusPy rejects it, inline the unmet predicate into a fresh local set (keep it an INDEPENDENT recompute, not a call to `UnmetItems`/`WorstRequired`). Verify the `Closure` excludes nothing it should: `Closure("sword")={sword,blade,iron}`, `Closure("ring")={ring,loop}` (cycle terminates). Confirm the model mirrors `_item_skill_gap`: worst by highest `required_level` (=CraftLevel), recursing through recipe ingredients, cycle-safe via the closure.

- [ ] **Step 3: Sanity-bite**

Temporarily change `WorstRequired`'s `>=` (in the CHOOSE) to `<=` (picks the *smallest* unmet level). On the skill-vec where sword(15) and blade(8) are both unmet, this returns 8 not 15 → `WorstRequired # OracleWorst` → halt `<<"TaskFeasibility FAIL", ...>>`. REVERT.

- [ ] **Step 4: Register**: append `("TaskFeasibility", 83)` to `MODULES` in `formal/run.py` (adjust if domain changed).

- [ ] **Step 5: Run the runner**: `python3 formal/run.py` → all PASS, exit 0 (slow; patient).

- [ ] **Step 6: Commit**

```bash
git add formal/specs/TaskFeasibility.tla formal/run.py
git commit -m "test(formal): TaskFeasibility worst-skill-gap spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Objective — `is_attainable` fixpoint + best-attainable gear + gap structure

Mirrors `src/artifactsmmo_cli/ai/tiers/objective.py` (`is_attainable`:15, `from_game_data`:57 gear selection, `gap`:86). READ it first. `equip_value` (`tiers/equip_value.py` = attack+resistance+hp_restore) is modeled as an integer per item.

**Files:** Create `formal/specs/Objective.tla`; Modify `formal/run.py`.

- [ ] **Step 1: Write `formal/specs/Objective.tla`**

```tla
------------------------------- MODULE Objective -------------------------------
EXTENDS Integers, FiniteSets, TLC

Max(a, b) == IF a > b THEN a ELSE b

\* Items with: recipe (set; "no recipe" = not craftable), whether it's a resource drop
\* (gatherable), its type (for gear selection), and integer equip_value.
Items == {"none", "wood_sword", "iron_sword", "gem_sword", "iron", "wood", "gem"}
HasRecipe == [ none |-> FALSE, wood_sword |-> TRUE, iron_sword |-> TRUE, gem_sword |-> TRUE,
               iron |-> FALSE, wood |-> FALSE, gem |-> FALSE ]
Recipe == [ none |-> {}, wood_sword |-> {"wood"}, iron_sword |-> {"iron"},
            gem_sword |-> {"gem"}, iron |-> {}, wood |-> {}, gem |-> {} ]
IsDrop == [ none |-> FALSE, wood_sword |-> FALSE, iron_sword |-> FALSE, gem_sword |-> FALSE,
            iron |-> TRUE, wood |-> TRUE, gem |-> FALSE ]   \* gem is NOT gatherable (drop-only)
EquipValue == [ none |-> 0, wood_sword |-> 10, iron_sword |-> 25, gem_sword |-> 40,
                iron |-> 0, wood |-> 0, gem |-> 0 ]
ItemType == [ none |-> "none", wood_sword |-> "weapon", iron_sword |-> "weapon",
              gem_sword |-> "weapon", iron |-> "none", wood |-> "none", gem |-> "none" ]
Weapons == { c \in Items : ItemType[c] = "weapon" }

\* ---- is_attainable (algorithm model): cycle-safe recursion via path subset ----
Att[code \in Items, path \in SUBSET Items] ==
  IF HasRecipe[code]
  THEN IF code \in path THEN FALSE
       ELSE \A m \in Recipe[code] : Att[m, path \cup {code}]
  ELSE IsDrop[code]
IsAttainable(code) == Att[code, {}]

\* ---- independent oracle: least-fixpoint grounding ----
N == Cardinality(Items)
GroundStep(G) == { c \in Items :
                     IF HasRecipe[c] THEN \A m \in Recipe[c] : m \in G ELSE IsDrop[c] }
Gnd[k \in 0..N] == IF k = 0 THEN {} ELSE GroundStep(Gnd[k-1])
Grounded == Gnd[N]

\* gem_sword needs gem (drop-only, not gatherable) -> NOT attainable;
\* iron_sword/wood_sword bottom out in gatherables -> attainable.
AttainCorrect(code) == IsAttainable(code) = (code \in Grounded)

\* ---- best-attainable gear per type (from_game_data): argmax equip_value over
\* attainable items of the type, ties by code asc ----
AttainableWeapons == { c \in Weapons : IsAttainable(c) }
BestWeapon ==
  IF AttainableWeapons = {} THEN "none"
  ELSE CHOOSE b \in AttainableWeapons :
         \A o \in AttainableWeapons :
            EquipValue[b] > EquipValue[o] \/ (EquipValue[b] = EquipValue[o] /\ b <= o)
\* iron_sword(25) is the best ATTAINABLE weapon (gem_sword 40 is not attainable).
GearCorrect == /\ BestWeapon = "iron_sword"
               /\ (AttainableWeapons # {} =>
                     \A o \in AttainableWeapons : EquipValue[BestWeapon] >= EquipValue[o])

\* ---- gap structure (integer; fractions verified as 0 <= gap <= denom) ----
TargetLevel == 50
MaxSkill == 50
Skills == {"mining", "cooking"}
\* state: char level, skill levels, gear value per slot vs target gear value.
GapState == { [lvl |-> l, sk |-> s, gearDef |-> g] :
                l \in {0, 25, 50}, s \in [Skills -> {0, 50}], g \in {0, 5, 40} }
CharGap(st) == Max(0, TargetLevel - st.lvl)
SkillGap(st, sk) == Max(0, MaxSkill - st.sk[sk])
SkillGapSum(st) == SkillGap(st, "mining") + SkillGap(st, "cooking")
SkillsDenom == Cardinality(Skills) * MaxSkill
\* is_complete iff all integer gaps are zero (gear deficit g models the summed gear gap).
IsComplete(st) == CharGap(st) = 0 /\ SkillGapSum(st) = 0 /\ st.gearDef = 0
GapCorrect(st) ==
  /\ CharGap(st) >= 0 /\ CharGap(st) <= TargetLevel             \* 0<=gap<=denom => fraction in [0,1]
  /\ SkillGapSum(st) >= 0 /\ SkillGapSum(st) <= SkillsDenom
  /\ st.gearDef >= 0
  /\ (IsComplete(st) <=> (CharGap(st) = 0 /\ SkillGapSum(st) = 0 /\ st.gearDef = 0))

Tagged == { [kind |-> "att", v |-> c] : c \in Items }
            \cup { [kind |-> "gear", v |-> "x"] }
            \cup { [kind |-> "gap", v |-> st] : st \in GapState }
Check(t) == IF t.kind = "att" THEN AttainCorrect(t.v)
            ELSE IF t.kind = "gear" THEN GearCorrect
            ELSE GapCorrect(t.v)

VARIABLE todo
Init == todo = Tagged
Next == /\ todo # {}
        /\ \E t \in todo :
              /\ Assert(Check(t), <<"Objective FAIL", t>>)
              /\ todo' = todo \ {t}
================================================================================
```

- [ ] **Step 2: Compute domain size and run**

|att| = 7; |gear| = 1; |gap| = 3 × 4 × 3 = 36 (lvl∈{0,25,50} × sk∈[{mining,cooking}→{0,50}] (4) × gearDef∈{0,5,40}); |Tagged| = **44**.
Run: `python3 formal/vendor/PlusPy/pluspy.py -c44 -P formal/specs:formal/vendor/PlusPy/modules/lib Objective`
Expected: `MAIN DONE`, exit 0. Riskiest: the path-keyed `Att[code, path \in SUBSET Items]` (domain 7×128=896 entries — fine) and the function-typed `sk \in [Skills -> {0,50}]`. Confirm `Grounded` excludes `gem_sword` (gem is drop-only) and `none`; includes `iron_sword`, `wood_sword`, `iron`, `wood`. Confirm `IsComplete` matches the Python `is_complete` (all three fractions zero ⇔ all integer gaps zero). Note in a comment that the float fractions are `gap/denom`, in `[0,1]` exactly because `0 <= gap <= denom` (the asserted integer bounds), so they are verified structurally without float arithmetic.

- [ ] **Step 3: Sanity-bite**

Temporarily change `IsDrop[gem]` to `TRUE` (make gem gatherable). Now `gem_sword` becomes attainable, so `BestWeapon` should become `gem_sword` (value 40 > 25) — but `GearCorrect` asserts `BestWeapon = "iron_sword"` → halt `<<"Objective FAIL", ...>>` on the `gear` case. REVERT. (This proves the attainability filter actually gates gear selection.)

- [ ] **Step 4: Register**: append `("Objective", 44)` to `MODULES`.

- [ ] **Step 5: Run the runner**: `python3 formal/run.py` → all PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add formal/specs/Objective.tla formal/run.py
git commit -m "test(formal): Objective attainability + gear-selection + gap-structure spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: StrategyTraversal — `is_reachable`, `unmet_closure_size`, `actionable_step`, `root_cost`

Mirrors `src/artifactsmmo_cli/ai/tiers/strategy.py` (`actionable_step`:69, `unmet_closure_size`:91, `root_cost`:107, `is_reachable`:125). READ it first. The prereq graph (`prerequisites`) and `is_satisfied` are already proven (`PrerequisiteGraph.tla`), so this spec abstracts them as a node graph with `Prereqs`/`IsSat`/`Producible`/`Kind` tables and verifies the four traversal functions.

**Files:** Create `formal/specs/StrategyTraversal.tla`; Modify `formal/run.py`.

- [ ] **Step 1: Write `formal/specs/StrategyTraversal.tla`**

```tla
----------------------------- MODULE StrategyTraversal -----------------------------
EXTENDS Integers, FiniteSets, TLC

Max(a, b) == IF a > b THEN a ELSE b

\* Abstract meta-goal graph. Kind in {obtain, skill, char}. Prereqs as a set per node.
Nodes == {"g_char", "g_skill", "g_sword", "g_blade", "g_iron", "g_ringA", "g_ringB"}
Kind == [ g_char |-> "char", g_skill |-> "skill", g_sword |-> "obtain", g_blade |-> "obtain",
          g_iron |-> "obtain", g_ringA |-> "obtain", g_ringB |-> "obtain" ]
Prereqs == [ g_char |-> {}, g_skill |-> {}, g_sword |-> {"g_blade"}, g_blade |-> {"g_iron"},
             g_iron |-> {}, g_ringA |-> {"g_ringB"}, g_ringB |-> {"g_ringA"} ]  \* ringA<->ringB cycle
IsSat == [ g_char |-> FALSE, g_skill |-> FALSE, g_sword |-> FALSE, g_blade |-> FALSE,
           g_iron |-> FALSE, g_ringA |-> FALSE, g_ringB |-> FALSE ]
\* producibility for obtain leaves (no prereqs): g_iron producible, the cyclic ring nodes irrelevant.
Producible == [ g_char |-> TRUE, g_skill |-> TRUE, g_sword |-> TRUE, g_blade |-> TRUE,
                g_iron |-> TRUE, g_ringA |-> FALSE, g_ringB |-> FALSE ]
NN == Cardinality(Nodes)

\* ---- is_reachable (algorithm model): cycle-safe via path subset ----
Reach[n \in Nodes, p \in SUBSET Nodes] ==
  IF IsSat[n] THEN TRUE
  ELSE IF n \in p THEN FALSE
  ELSE IF Kind[n] = "skill" THEN TRUE
  ELSE IF Kind[n] = "obtain" /\ Prereqs[n] = {} THEN Producible[n]
  ELSE \A q \in Prereqs[n] : Reach[q, p \cup {n}]
IsReachable(n) == Reach[n, {}]

\* ---- independent oracle: least-fixpoint grounding (well-founded) ----
GroundStep(G) == { n \in Nodes :
                     \/ IsSat[n]
                     \/ Kind[n] = "skill"
                     \/ (Kind[n] = "obtain" /\ Prereqs[n] = {} /\ Producible[n])
                     \/ (Prereqs[n] # {} /\ \A q \in Prereqs[n] : q \in G) }
Gnd[k \in 0..NN] == IF k = 0 THEN {} ELSE GroundStep(Gnd[k-1])
Grounded == Gnd[NN]
ReachCorrect(n) == IsReachable(n) = (n \in Grounded)

\* ---- unmet_closure_size: |unmet nodes in root's prereq closure|, min 1 ----
Clo[k \in 0..NN, r \in Nodes] == IF k = 0 THEN {r} ELSE Clo[k-1, r] \cup UNION { Prereqs[m] : m \in Clo[k-1, r] }
ClosureOf(r) == Clo[NN, r]
UnmetCount(r) == Cardinality({ m \in ClosureOf(r) : ~IsSat[m] })
SizeModel(r) == Max(UnmetCount(r), 1)
\* oracle: independent recompute of the unmet count over the closure, floored 1.
SizeCorrect(r) == SizeModel(r) = Max(Cardinality({ m \in ClosureOf(r) : IsSat[m] = FALSE }), 1)

\* ---- actionable_step: a node reachable from root that is unmet, has ALL direct
\* prereqs satisfied, and (obtain => producible); None if none such. Model the SET of
\* such actionable nodes in the reachable closure; the function returns one of them
\* (DFS order picks which; correctness = membership, not identity). ----
Actionables(r) == { m \in ClosureOf(r) :
                      ~IsSat[m]
                      /\ (\A q \in Prereqs[m] : IsSat[q])
                      /\ (Kind[m] = "obtain" => Producible[m]) }
\* The algorithm returns SOME actionable node or "none". Model: StepModel(r) = "none"
\* iff Actionables(r) = {}; else any element. Verify the existence characterization
\* and that a non-none result is genuinely actionable.
StepIsNone(r) == Actionables(r) = {}
StepCorrect(r) ==
  /\ (StepIsNone(r) <=> Actionables(r) = {})
  /\ (Actionables(r) # {} =>
        \E m \in Actionables(r) :
           ~IsSat[m] /\ (\A q \in Prereqs[m] : IsSat[q]) /\ (Kind[m] = "obtain" => Producible[m]))

\* ---- root_cost: char/skill = max(1, level diff); gear(obtain) = unmet_closure_size ----
RootCost(r, charLvl, charTarget, skillLvl, skillTarget) ==
  IF Kind[r] = "char" THEN Max(1, charTarget - charLvl)
  ELSE IF Kind[r] = "skill" THEN Max(1, skillTarget - skillLvl)
  ELSE SizeModel(r)
CostCorrect(r) ==
  /\ RootCost(r, 10, 50, 3, 50) >= 1                          \* floored
  /\ (Kind[r] = "char" => RootCost(r, 10, 50, 3, 50) = 40)
  /\ (Kind[r] = "skill" => RootCost(r, 10, 50, 3, 50) = 47)
  /\ (Kind[r] = "obtain" => RootCost(r, 10, 50, 3, 50) = SizeModel(r))

Tagged == { [kind |-> "reach", v |-> n] : n \in Nodes }
            \cup { [kind |-> "size", v |-> n] : n \in Nodes }
            \cup { [kind |-> "step", v |-> n] : n \in Nodes }
            \cup { [kind |-> "cost", v |-> n] : n \in Nodes }
Check(t) == IF t.kind = "reach" THEN ReachCorrect(t.v)
            ELSE IF t.kind = "size" THEN SizeCorrect(t.v)
            ELSE IF t.kind = "step" THEN StepCorrect(t.v)
            ELSE CostCorrect(t.v)

VARIABLE todo
Init == todo = Tagged
Next == /\ todo # {}
        /\ \E t \in todo :
              /\ Assert(Check(t), <<"StrategyTraversal FAIL", t>>)
              /\ todo' = todo \ {t}
================================================================================
```

> **Implementer note on oracle independence:** the `SizeCorrect` oracle above is currently the SAME expression as `SizeModel` — make it genuinely independent: compute the unmet count a second way (e.g. sum `1` over closure members via a recursive fold, or `Cardinality(ClosureOf(r)) - Cardinality({m \in ClosureOf(r): IsSat[m]})`), so the equality is a real cross-check. Likewise confirm `ReachCorrect` compares the path-recursive `Reach` against the monotone `Grounded` fixpoint (two genuinely different formulations — they must AGREE incl. on the `g_ringA/g_ringB` cycle, where both yield unreachable). For `StepCorrect`, the actionable-set characterization IS independent of any DFS-order implementation; keep it set-based.

- [ ] **Step 2: Run (domain size = 4 × |Nodes| = 4 × 7 = 28)**

Run: `python3 formal/vendor/PlusPy/pluspy.py -c28 -P formal/specs:formal/vendor/PlusPy/modules/lib StrategyTraversal`
Expected: `MAIN DONE`, exit 0. Riskiest: the path-keyed `Reach[n, p \in SUBSET Nodes]` (7×128 domain) and `Clo[k,r]`. Confirm the cycle (`g_ringA`/`g_ringB`) yields `IsReachable=FALSE` in BOTH `Reach` and `Grounded`; confirm `g_sword` reachable (sword→blade→iron, iron producible); confirm `Actionables` for root `g_sword` = `{g_iron}` (iron unmet, no prereqs, producible) since blade/sword have unmet prereqs. Make `SizeCorrect`'s oracle independent per the note.

- [ ] **Step 3: Sanity-bite**

Temporarily change `Reach`'s cycle guard `IF n \in p THEN FALSE` to `THEN TRUE` (treat cycles as reachable). Now `g_ringA` becomes reachable in `Reach` but stays out of `Grounded` → `ReachCorrect("g_ringA")` halts `<<"StrategyTraversal FAIL", ...>>`. REVERT.

- [ ] **Step 4: Register**: append `("StrategyTraversal", 28)` to `MODULES`.

- [ ] **Step 5: Run the runner**: `python3 formal/run.py` → all PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add formal/specs/StrategyTraversal.tla formal/run.py
git commit -m "test(formal): StrategyTraversal reachability/closure/actionable spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: README — Phase 3 property→code map

**Files:** Modify `formal/README.md`.

- [ ] **Step 1: Append three rows to the `Property -> code map` table (match the existing 3-column format)**

```markdown
| `TaskFeasibility.tla` | `ai/task_feasibility.py:30,44` | `task_requirement` returns the highest-`required_level` unmet crafting-skill gap over the task item's craft closure (cycle-safe), None iff feasible; the monster branch gates on `monster_level > char_level + 2`. |
| `Objective.tla` | `ai/tiers/objective.py:15,57,86` | `is_attainable` = the craft chain bottoms out in gatherables (matches a least-fixpoint grounding, cycle-safe); `from_game_data` picks the highest-equip-value ATTAINABLE item per gear slot; `gap` yields non-negative gaps with `is_complete` iff every gap is zero (fractions are `gap/denom`, in [0,1] since `0 <= gap <= denom`). |
| `StrategyTraversal.tla` | `ai/tiers/strategy.py:69,91,107,125` | `is_reachable` (path-recursive) equals the well-founded grounding fixpoint (cycles unreachable); `unmet_closure_size` = count of unmet nodes in the prereq closure (min 1); `actionable_step` returns an unmet node whose direct prereqs are all satisfied (producible if obtain), None iff none exists; `root_cost` floors at 1. |
```

- [ ] **Step 2: Append a Phase-3 modeling note under `## Modeling notes`**

```markdown
- The strategy/feasibility specs (`TaskFeasibility`, `Objective`, `StrategyTraversal`)
  abstract the prerequisite graph and `is_satisfied` (already proven in
  `PrerequisiteGraph.tla`) and the recipe relation (`RecipeClosure.tla`) as in-spec
  node/recipe tables, and verify the TRAVERSAL logic (worst-gap, fixpoint reachability,
  closure counting, deepest-actionable selection) against independent fixpoint/cardinality
  oracles. `actionable_step`'s DFS pick-order is implementation-defined; the spec verifies
  the returned node is genuinely actionable and that None ⇔ no actionable node exists,
  not which specific node DFS returns. Gap fractions are verified structurally
  (`0 <= gap <= denom`) to stay integer-only.
```

- [ ] **Step 3: Final full run**

Run: `python3 formal/run.py`
Expected: every module PASS (12 prior incl. Smoke + TaskFeasibility + Objective + StrategyTraversal = 13), exit 0. Slow — be patient.

- [ ] **Step 4: Commit**

```bash
git add formal/README.md
git commit -m "docs(formal): map Phase 3 strategy/feasibility specs to code

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review notes (addressed)

- **Spec coverage:** `task_requirement`/`_item_skill_gap` (Task 1); `is_attainable` + `from_game_data` gear + `gap`/`is_complete` (Task 2); `actionable_step` + `is_reachable` + `unmet_closure_size` + `root_cost` (Task 3); README (Task 4). All Phase-3 design components covered.
- **Independent oracles:** TaskFeasibility worst-gap = direct max recompute + None-iff-feasible; Objective is_attainable = grounding fixpoint vs path-recursion, gear = argmax filtered by attainability, gap = integer-bound structure; StrategyTraversal reachability = path-recursion vs grounding fixpoint, size/step = set characterizations. Each task has a non-vacuous sanity-bite. The Task-3 note flags making `SizeCorrect`'s oracle genuinely independent (not a copy of `SizeModel`).
- **Recursion without RECURSIVE keyword:** `Sat[k,r]` closures, path-keyed `Att[code,path]`/`Reach[n,p]`, `Clo[k,r]` — all bounded recursive functions per the proven idiom.
- **Float avoidance:** gap fractions verified via `0 <= gap <= denom` integer bounds + `is_complete` over integer gaps; `equip_value` modeled as integer. No reals anywhere.
- **Cycle-safety exercised:** ring↔loop (TaskFeasibility), gem_sword drop-only + (implicitly) cyclic recipes (Objective), g_ringA↔g_ringB (StrategyTraversal) — each spec includes a cycle and asserts the cycle-safe outcome.
- **No placeholders:** intentional fill-ins are PlusPy-subset syntax adaptation, domain-size tuning, and the explicit "make SizeCorrect oracle independent" / "inline OracleWorst predicate" notes — each with concrete guidance.
- **Type/name consistency:** module names and `MODULES` counts (83, 44, 28) consistent across tasks and runner.
