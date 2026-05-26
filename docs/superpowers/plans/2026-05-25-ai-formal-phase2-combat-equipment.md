# AI Formal Verification — Phase 2 (Combat/Equipment) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two TLA+/PlusPy specs to the existing `formal/` harness proving the correctness of the equipment-selection components that feed `predict_win`'s best-on-hand-loadout verdict: `equipment/scoring.pick_loadout` (with `weapon_score`/`armor_score`) and `equipment/projection.project_loadout_stats`.

**Architecture:** Same enumerate-and-`Assert`-against-independent-oracle technique and harness as the seven existing specs. Scores are floats in Python (`atk*(1-res/100)`); since `pick_loadout` only ever *compares* scores, the spec uses an **order-preserving integer surrogate** (`Σ atk*max(0,100-res)` = `100 ×` the real weapon score; `Σ mon_atk*armor_res` = `100 ×` the real armor score) so PlusPy never touches floats while proving exactly the ordering the code depends on. Projection stats are already integers.

**Tech Stack:** TLA+ (PlusPy subset), PlusPy (vendored at `formal/vendor/PlusPy`), Python 3.13 stdlib runner.

---

## Critical environment facts (apply to every task)

- PlusPy entry: `python3 formal/vendor/PlusPy/pluspy.py`. If `formal/vendor/` missing, run `./formal/setup.sh`.
- Manual run for module `M`, domain size `N`:
  `python3 formal/vendor/PlusPy/pluspy.py -c<N> -P formal/specs:formal/vendor/PlusPy/modules/lib <M>`
- CLEAN run prints `MAIN DONE`, exit 0. FAILED `Assert` prints `Evaluating Assert (...) failed` + `AssertionError`, exit 1.
- Runner: `python3 formal/run.py` (NOT `uv run` in the worktree). Append `(name, domain_size)` to `MODULES`.
- **Work in the worktree path you are given and verify files land there** (`git -C <worktree> status`) before running pluspy — a prior task hit a Write that resolved to the main checkout.
- **PlusPy has NO `RECURSIVE` operator keyword** — use recursive functions `f[k \in S]==...`. Supports ASSUME, records, functions, set comprehension, UNION, SUBSET, DOMAIN, Cardinality (EXTENDS FiniteSets), CHOOSE, `\E`/`\A`, `LET`/`IF`, integer arithmetic. **No reals/floats** — keep everything integer.
- The intended `.tla` is the CONTRACT; adapt surface syntax to PlusPy's subset but do NOT weaken any asserted property. If a property truly can't be expressed after real effort, report BLOCKED — never fake a pass.
- Enumeration idiom: `VARIABLE todo`; `Init == todo = <domain>`; `Next == /\ todo # {} /\ \E x \in todo : /\ Assert(Correct(x), <<"M FAIL", x>>) /\ todo' = todo \ {x}`; run `-c|domain|`.

## File structure

- Create `formal/specs/EquipmentScoring.tla` (weapon/armor score surrogate + `pick_loadout`)
- Create `formal/specs/LoadoutProjection.tla` (`project_loadout_stats`)
- Modify `formal/run.py` (+2 MODULES entries)
- Modify `formal/README.md` (+2 property→code rows)

---

## Task 1: EquipmentScoring — score ordering + `pick_loadout` per-slot argmax + no-downgrade

Mirrors `src/artifactsmmo_cli/ai/equipment/scoring.py` (`weapon_score`:9, `armor_score`:23, `_candidates_for_slot`:33, `pick_loadout`:55). READ that file first.

**Key modeling decision (floats → integers):** `pick_loadout` uses `weapon_score`/`armor_score` only inside `max(...)` and a strict `>` comparison. The real scores are `Σ atk*(1-res/100)` and `Σ mon_atk*res/100`. The integer surrogates `WScore = Σ atk*max(0,100-res)` and `AScore = Σ mon_atk*armor_res` are each exactly `100×` the real score, so they induce the **identical ordering** (argmax and strict `>`). The spec verifies the properties `pick_loadout` actually relies on (score-optimal per slot, no-downgrade, feasibility) using the surrogate; the float formula's only role is that ordering, which the surrogate preserves. (Note in a comment that `max(0, ...)` matches `weapon_score`'s `max(0.0, 1-res/100)` clamp; `armor_score` has no clamp, and neither does `AScore`.)

**Files:** Create `formal/specs/EquipmentScoring.tla`; Modify `formal/run.py`.

- [ ] **Step 1: Write `formal/specs/EquipmentScoring.tla`**

```tla
----------------------------- MODULE EquipmentScoring -----------------------------
EXTENDS Integers, FiniteSets, TLC

Elements == {"fire", "earth"}
Max(a, b) == IF a > b THEN a ELSE b

\* Slots and the type->slots map (subset of ITEM_TYPE_TO_SLOTS).
SlotsOfType == [ weapon |-> {"weapon_slot"}, body |-> {"body_slot"}, helmet |-> {"helmet_slot"} ]
AllSlots == {"weapon_slot", "body_slot", "helmet_slot"}

\* Item universe with attributes. "none" is the empty-slot sentinel (level 0 etc).
Items == {"none", "wood_sword", "iron_sword", "leather", "plate", "cap"}
Type   == [ none |-> "none", wood_sword |-> "weapon", iron_sword |-> "weapon",
            leather |-> "body", plate |-> "body", cap |-> "helmet" ]
Level  == [ none |-> 0, wood_sword |-> 1, iron_sword |-> 5, leather |-> 1, plate |-> 8, cap |-> 1 ]
Attack == [ none |-> [fire |-> 0, earth |-> 0], wood_sword |-> [fire |-> 6, earth |-> 0],
            iron_sword |-> [fire |-> 10, earth |-> 0], leather |-> [fire |-> 0, earth |-> 0],
            plate |-> [fire |-> 0, earth |-> 0], cap |-> [fire |-> 0, earth |-> 0] ]
Resist == [ none |-> [fire |-> 0, earth |-> 0], wood_sword |-> [fire |-> 0, earth |-> 0],
            iron_sword |-> [fire |-> 0, earth |-> 0], leather |-> [fire |-> 5, earth |-> 2],
            plate |-> [fire |-> 20, earth |-> 10], cap |-> [fire |-> 3, earth |-> 0] ]

\* ---- integer score surrogates (order-equivalent to the float scores) ----
WScore(item, monRes) == LET S(e) == Attack[item][e] * Max(0, 100 - monRes[e])
                        IN S("fire") + S("earth")
AScore(item, monAtk) == LET S(e) == monAtk[e] * Resist[item][e]
                        IN S("fire") + S("earth")
ScoreOf(item, slot, monAtk, monRes) ==
  IF slot = "weapon_slot" THEN WScore(item, monRes) ELSE AScore(item, monAtk)

\* state: level (char), inv (code->qty), equip (slot->code, "none" if empty).
Owned(st) == { c \in DOMAIN st.inv : st.inv[c] > 0 }
              \cup { st.equip[s] : s \in AllSlots }
Feasible(st, c) == c # "none" /\ st.level >= Level[c]
Candidates(st, slot) ==
  { c \in Owned(st) : Feasible(st, c) /\ slot \in SlotsOfType[Type[c]] }

\* ---- pick_loadout per-slot result (algorithm model) ----
PickSlot(st, slot, monAtk, monRes) ==
  LET cands == Candidates(st, slot)
      cur   == st.equip[slot]
  IN IF cands = {} THEN cur
     ELSE LET best == CHOOSE b \in cands :
                        \A o \in cands : ScoreOf(b, slot, monAtk, monRes) >= ScoreOf(o, slot, monAtk, monRes)
          IN IF cur = best THEN cur
             ELSE IF cur = "none" THEN best
             ELSE IF ScoreOf(best, slot, monAtk, monRes) > ScoreOf(cur, slot, monAtk, monRes)
                  THEN best ELSE cur

\* ---- independent oracle ----
MaxScore(st, slot, monAtk, monRes) ==
  LET cands == Candidates(st, slot)
  IN CHOOSE v \in { ScoreOf(c, slot, monAtk, monRes) : c \in cands } :
       \A c \in cands : v >= ScoreOf(c, slot, monAtk, monRes)

SlotCorrect(st, slot, monAtk, monRes) ==
  LET r == PickSlot(st, slot, monAtk, monRes)
      cands == Candidates(st, slot)
      cur == st.equip[slot]
  IN IF cands = {}
     THEN r = cur                                   \* no candidates => unchanged
     ELSE /\ ScoreOf(r, slot, monAtk, monRes) = MaxScore(st, slot, monAtk, monRes)  \* score-optimal
          /\ ScoreOf(r, slot, monAtk, monRes) >= ScoreOf(cur, slot, monAtk, monRes) \* no downgrade
          /\ (r # "none" => Feasible(st, r) /\ slot \in SlotsOfType[Type[r]])        \* feasible pick
          /\ (r # cur => r \in cands)                \* a change is always to a real candidate
          /\ (ScoreOf(cur, slot, monAtk, monRes) = MaxScore(st, slot, monAtk, monRes) => r = cur) \* ties keep current

\* hand states + a fixed monster, covering: empty candidates, upgrade, tie-keeps-current,
\* below-level exclusion, empty-slot fill, downgrade rejection.
MonAtk == [fire |-> 20, earth |-> 10]
MonRes == [fire |-> 0, earth |-> 0]
States == {
  \* s1: owns iron_sword (better) while wood_sword equipped -> upgrade weapon_slot
  [level |-> 5, inv |-> [iron_sword |-> 1], equip |-> [weapon_slot |-> "wood_sword", body_slot |-> "none", helmet_slot |-> "none"]],
  \* s2: owns iron_sword but level 4 < 5 -> excluded, keep wood_sword
  [level |-> 4, inv |-> [iron_sword |-> 1], equip |-> [weapon_slot |-> "wood_sword", body_slot |-> "none", helmet_slot |-> "none"]],
  \* s3: empty body_slot, owns leather -> fill it
  [level |-> 3, inv |-> [leather |-> 1], equip |-> [weapon_slot |-> "wood_sword", body_slot |-> "none", helmet_slot |-> "none"]],
  \* s4: plate equipped (better armor) + leather owned -> no downgrade to leather
  [level |-> 8, inv |-> [leather |-> 1], equip |-> [weapon_slot |-> "none", body_slot |-> "plate", helmet_slot |-> "none"]],
  \* s5: no candidates for any slot (empty inventory, empty equip)
  [level |-> 5, inv |-> [none |-> 0], equip |-> [weapon_slot |-> "none", body_slot |-> "none", helmet_slot |-> "none"]]
}

Correct(st) == \A slot \in AllSlots : SlotCorrect(st, slot, MonAtk, MonRes)

VARIABLE todo
Init == todo = States
Next == /\ todo # {}
        /\ \E st \in todo :
              /\ Assert(Correct(st), <<"EquipmentScoring FAIL", st>>)
              /\ todo' = todo \ {st}
================================================================================
```

- [ ] **Step 2: Run (domain size = |States| = 5)**

Run: `python3 formal/vendor/PlusPy/pluspy.py -c5 -P formal/specs:formal/vendor/PlusPy/modules/lib EquipmentScoring`
Expected: `MAIN DONE`, exit 0. Iterate on PlusPy-subset syntax (nested records, `CHOOSE` argmax, `Owned`'s set-image `{st.equip[s] : s \in AllSlots}`) until clean. If `Candidates` empty-set feeds `MaxScore`'s `CHOOSE v \in {} : ...`, guard it — `SlotCorrect` only calls `MaxScore` in the `cands # {}` branch, so the empty case is never evaluated; confirm PlusPy short-circuits the `IF` (it does — only the taken branch is evaluated).

- [ ] **Step 3: Sanity-bite (prove non-vacuous)**

Temporarily change `PickSlot`'s strict `>` to `>=` (swap on ties / equal score). On state s4 (`plate` equipped, `leather` owned, both feasible) this only bites if scores differ — instead, to guarantee a bite, change the no-downgrade: make `PickSlot` always return `best` (drop the `cur`/strict-improvement logic). Run; expect a halt `<<"EquipmentScoring FAIL", ...>>` on s2 (would pick below-level via... no) or s4 (downgrade plate→... ). Concretely: on s4, dropping no-downgrade makes it pick whichever of {plate,leather} the CHOOSE returns; if it returns leather (score 0 vs plate's positive) the `no-downgrade` conjunct fails. To force determinism, instead break the oracle's score-optimal check: temporarily change `MaxScore`'s `>=` to `>` (making `CHOOSE` find no maximum on singletons) — simplest reliable bite: change one `States` entry's expectation indirectly by mutating `WScore` to `S("fire") + S("earth") + 1` so `ScoreOf(r)=MaxScore` still holds (both shift) — NO. **Use this definite bite:** temporarily add a conjunct to `SlotCorrect` that is false, e.g. `/\ r = "nonexistent"`, confirm it fails, then REVERT. (The goal is only to confirm the harness/Assert wiring fires; the structural properties are already exercised by s1–s5.)

> Reviewer/implementer: prefer a *semantic* bite if you can construct one (e.g. add an item that is a strictly better weapon but below level, and assert it is NOT chosen — then temporarily remove the level filter and watch it fail). Use the trivial `r = "nonexistent"` bite only as a last resort to prove the assertion is evaluated.

- [ ] **Step 4: Register in the runner**

In `formal/run.py`, append: `("EquipmentScoring", 5)`.

- [ ] **Step 5: Run the runner**

Run: `python3 formal/run.py` — expect all PASS, exit 0 (slow, several minutes; be patient).

- [ ] **Step 6: Commit**

```bash
git add formal/specs/EquipmentScoring.tla formal/run.py
git commit -m "test(formal): EquipmentScoring argmax + no-downgrade spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: LoadoutProjection — additive delta model for `project_loadout_stats`

Mirrors `src/artifactsmmo_cli/ai/equipment/projection.py:30`. All stats are integers. READ the file first.

**Files:** Create `formal/specs/LoadoutProjection.tla`; Modify `formal/run.py`.

- [ ] **Step 1: Write `formal/specs/LoadoutProjection.tla`**

```tla
----------------------------- MODULE LoadoutProjection -----------------------------
EXTENDS Integers, FiniteSets, TLC

Elements == {"fire", "earth"}
Slots == {"weapon_slot", "body_slot"}

\* Item contributions (integers). "none" contributes nothing.
Items == {"none", "w1", "w2", "b1", "b2"}
IAtk  == [ none |-> [fire |-> 0, earth |-> 0], w1 |-> [fire |-> 5, earth |-> 0],
           w2 |-> [fire |-> 9, earth |-> 1], b1 |-> [fire |-> 0, earth |-> 0], b2 |-> [fire |-> 0, earth |-> 0] ]
IResist == [ none |-> [fire |-> 0, earth |-> 0], w1 |-> [fire |-> 0, earth |-> 0],
             w2 |-> [fire |-> 0, earth |-> 0], b1 |-> [fire |-> 4, earth |-> 2], b2 |-> [fire |-> 10, earth |-> 6] ]
IHp   == [ none |-> 0, w1 |-> 0, w2 |-> 0, b1 |-> 12, b2 |-> 30 ]
IInit == [ none |-> 0, w1 |-> 2, w2 |-> 5, b1 |-> 0, b2 |-> 0 ]

\* current totals (server-reported base+equipped) + the equipped loadout.
\* state: atk[e], res[e], maxhp, init, equip[slot]->code.
\* For brevity model the element-vector fields (attack, resistance) + max_hp + initiative;
\* the scalar fields (dmg, dmg_elements, critical_strike) follow the identical additive
\* pattern and are covered by the same proof shape (note in a comment).
Field == {"fire", "earth"}  \* attack/resistance element keys

\* delta of swapping old->new on one slot, per element-attack:
DAtk(new, old, e) == IAtk[new][e] - IAtk[old][e]
DRes(new, old, e) == IResist[new][e] - IResist[old][e]
DHp(new, old)  == IHp[new] - IHp[old]
DInit(new, old) == IInit[new] - IInit[old]

\* ---- algorithm model: project (sum deltas over changed slots) ----
ChangedSlots(st, loadout) == { s \in Slots : loadout[s] # st.equip[s] }
ProjAtk(st, loadout, e) ==
  st.atk[e] + LET contrib(s) == DAtk(loadout[s], st.equip[s], e)
              IN LET cs == ChangedSlots(st, loadout)
                 IN IF cs = {} THEN 0
                    ELSE LET seq == cs IN  \* sum over the (<=2) changed slots
                         (IF "weapon_slot" \in cs THEN contrib("weapon_slot") ELSE 0)
                         + (IF "body_slot" \in cs THEN contrib("body_slot") ELSE 0)
ProjRes(st, loadout, e) ==
  st.res[e] + (IF loadout["weapon_slot"] # st.equip["weapon_slot"] THEN DRes(loadout["weapon_slot"], st.equip["weapon_slot"], e) ELSE 0)
            + (IF loadout["body_slot"] # st.equip["body_slot"] THEN DRes(loadout["body_slot"], st.equip["body_slot"], e) ELSE 0)
ProjHp(st, loadout) ==
  st.maxhp + (IF loadout["weapon_slot"] # st.equip["weapon_slot"] THEN DHp(loadout["weapon_slot"], st.equip["weapon_slot"]) ELSE 0)
           + (IF loadout["body_slot"] # st.equip["body_slot"] THEN DHp(loadout["body_slot"], st.equip["body_slot"]) ELSE 0)
ProjInit(st, loadout) ==
  st.init + (IF loadout["weapon_slot"] # st.equip["weapon_slot"] THEN DInit(loadout["weapon_slot"], st.equip["weapon_slot"]) ELSE 0)
          + (IF loadout["body_slot"] # st.equip["body_slot"] THEN DInit(loadout["body_slot"], st.equip["body_slot"]) ELSE 0)

\* ---- independent oracle: full new-minus-old over ALL slots (not just changed) ----
\* Because new==old contributes a zero delta, summing over all slots equals summing
\* over changed slots. This is an INDEPENDENT formulation (no ChangedSlots guard).
OAtk(st, loadout, e) == st.atk[e] + (IAtk[loadout["weapon_slot"]][e] - IAtk[st.equip["weapon_slot"]][e])
                                  + (IAtk[loadout["body_slot"]][e]   - IAtk[st.equip["body_slot"]][e])
ORes(st, loadout, e) == st.res[e] + (IResist[loadout["weapon_slot"]][e] - IResist[st.equip["weapon_slot"]][e])
                                  + (IResist[loadout["body_slot"]][e]   - IResist[st.equip["body_slot"]][e])
OHp(st, loadout)  == st.maxhp + (IHp[loadout["weapon_slot"]] - IHp[st.equip["weapon_slot"]])
                              + (IHp[loadout["body_slot"]]   - IHp[st.equip["body_slot"]])
OInit(st, loadout) == st.init + (IInit[loadout["weapon_slot"]] - IInit[st.equip["weapon_slot"]])
                              + (IInit[loadout["body_slot"]]   - IInit[st.equip["body_slot"]])

Correct(c) ==
  LET st == c.st loadout == c.lo IN
  /\ \A e \in Field : ProjAtk(st, loadout, e) = OAtk(st, loadout, e)
  /\ \A e \in Field : ProjRes(st, loadout, e) = ORes(st, loadout, e)
  /\ ProjHp(st, loadout) = OHp(st, loadout)
  /\ ProjInit(st, loadout) = OInit(st, loadout)
  \* identity: loadout == equipment => projection == current totals
  /\ (loadout = st.equip =>
        /\ \A e \in Field : ProjAtk(st, loadout, e) = st.atk[e]
        /\ ProjHp(st, loadout) = st.maxhp)

\* enumerate states x loadouts: identity, single swap, double swap (composability),
\* unequip (->none), equip-into-empty (none->item), downgrade (negative delta).
BaseEquip == [weapon_slot |-> "w1", body_slot |-> "b1"]
BaseState == [atk |-> [fire |-> 5, earth |-> 0], res |-> [fire |-> 4, earth |-> 2],
              maxhp |-> 112, init |-> 2, equip |-> BaseEquip]
EmptyState == [atk |-> [fire |-> 0, earth |-> 0], res |-> [fire |-> 0, earth |-> 0],
               maxhp |-> 100, init |-> 0, equip |-> [weapon_slot |-> "none", body_slot |-> "none"]]
Loadouts == { [weapon_slot |-> w, body_slot |-> b] : w \in {"none","w1","w2"}, b \in {"none","b1","b2"} }
Cases == { [st |-> BaseState, lo |-> lo] : lo \in Loadouts }
           \cup { [st |-> EmptyState, lo |-> lo] : lo \in Loadouts }

VARIABLE todo
Init == todo = Cases
Next == /\ todo # {}
        /\ \E c \in todo :
              /\ Assert(Correct(c), <<"LoadoutProjection FAIL", c>>)
              /\ todo' = todo \ {c}
================================================================================
```

- [ ] **Step 2: Run (domain size = |Cases| = 2 states × 3×3 loadouts = 18)**

Run: `python3 formal/vendor/PlusPy/pluspy.py -c18 -P formal/specs:formal/vendor/PlusPy/modules/lib LoadoutProjection`
Expected: `MAIN DONE`, exit 0. The `ProjAtk` `LET ... IN LET ...` nesting is awkward — if PlusPy rejects it, simplify `ProjAtk` to the same two-`IF` shape as `ProjRes` (the `ChangedSlots`-guarded form must still be DISTINCT from the oracle `OAtk` which sums over all slots unconditionally — that distinctness is what makes it a real cross-check of "changed-slot guard == all-slot sum"). Keep the four field equalities + the identity conjunct.

- [ ] **Step 3: Sanity-bite (prove non-vacuous)**

Temporarily change `ProjHp` to add `+1` (`st.maxhp + 1 + ...`). Run; expect a halt `<<"LoadoutProjection FAIL", ...>>` (ProjHp ≠ OHp). Then REVERT.

- [ ] **Step 4: Register in the runner**

In `formal/run.py`, append: `("LoadoutProjection", 18)`.

- [ ] **Step 5: Run the runner**

Run: `python3 formal/run.py` — expect all PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add formal/specs/LoadoutProjection.tla formal/run.py
git commit -m "test(formal): LoadoutProjection additive-delta spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: README — Phase 2 property→code map

**Files:** Modify `formal/README.md`.

- [ ] **Step 1: Append two rows to the `Property -> code map` table (match the existing 3-column format `Spec | Pins | Property`)**

```markdown
| `EquipmentScoring.tla` | `ai/equipment/scoring.py:9,23,55` | `pick_loadout` picks, per slot independently, a score-optimal feasible owned item and never downgrades (swap only on strict score improvement; ties keep the current item; below-level items excluded). Scores use an integer surrogate order-equivalent to `weapon_score`/`armor_score`. |
| `LoadoutProjection.tla` | `ai/equipment/projection.py:30` | `project_loadout_stats` = current totals + Σ over changed slots of (new − old) per stat; equals the unconditional all-slot new−old sum (changed-slot guard is sound), and the identity loadout reproduces current stats exactly. |
```

- [ ] **Step 2: Append a Phase-2 modeling note under `## Modeling notes`**

```markdown
- The combat/equipment specs (`EquipmentScoring`, `LoadoutProjection`) keep all
  arithmetic integer. `EquipmentScoring` replaces the float `weapon_score`/`armor_score`
  (`atk*(1-res/100)`) with the order-preserving integer surrogate `atk*max(0,100-res)`
  — `pick_loadout` only compares scores, so the surrogate proves the exact ordering it
  relies on. `LoadoutProjection` models the integer stat fields (attack/resistance
  elements, max_hp, initiative); the remaining scalar fields (dmg, dmg_elements,
  critical_strike) follow the identical additive pattern.
```

- [ ] **Step 3: Final full run**

Run: `python3 formal/run.py`
Expected: every module PASS (the 5 originals + TaskBatch, InventoryCaps, BankSelection, EquipmentScoring, LoadoutProjection = 10), exit 0. Slow — be patient.

- [ ] **Step 4: Commit**

```bash
git add formal/README.md
git commit -m "docs(formal): map Phase 2 combat/equipment specs to code

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review notes (addressed)

- **Spec coverage:** both Phase-2 components get a task (1–2); README task (3). `weapon_score`/`armor_score` are covered inside Task 1 (the surrogate + the ordering they induce in `pick_loadout`).
- **Float avoidance:** the integer-surrogate decision is documented in the plan, Task 1, and the README note; it preserves exactly the ordering `pick_loadout` uses (argmax + strict `>`), which is the only thing the float scores feed.
- **Independent oracles:** EquipmentScoring oracle = `MaxScore` recomputed directly + structural conjuncts (feasible/no-downgrade/ties-keep-current), NOT a copy of `PickSlot`. LoadoutProjection oracle = unconditional all-slot new−old sum, structurally distinct from the `ChangedSlots`-guarded `Proj*` (proves the guard is sound) + the identity property. Each task has a non-vacuous sanity-bite.
- **Tie-order independence:** `pick_loadout`'s Python `max` over a set-derived list has nondeterministic tie-breaking; the spec asserts the chosen item's *score* is maximal (+ ties keep current), never a specific tie-winner — so it is robust to that nondeterminism.
- **No placeholders:** intentional fill-ins are PlusPy-subset syntax adaptation and the preferred-vs-fallback sanity-bite in Task 1 Step 3, each with explicit guidance.
- **Type/name consistency:** module names and `MODULES` counts (5, 18) consistent across tasks and runner; `WScore`/`AScore`/`ScoreOf`/`PickSlot`/`Candidates` used consistently.
