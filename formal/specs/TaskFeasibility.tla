------------------------------- MODULE TaskFeasibility -------------------------------
EXTENDS Integers, FiniteSets, TLC

\* Mirrors src/artifactsmmo_cli/ai/task_feasibility.py:
\*   task_requirement (monster threshold branch) and _item_skill_gap (worst unmet
\*   crafting-skill gap over the recipe closure, recursing ingredients, cycle-safe
\*   via the `seen` visited guard). The "worst" gap is the one with the highest
\*   required_level (= CraftLevel) among items whose craft skill is below the
\*   character's current level. None (here: 0) iff the task is already feasible.

MonsterMargin == 2
Max(a, b) == IF a > b THEN a ELSE b

Items == {"sword", "blade", "iron", "ring", "loop"}
CraftSkill == [ sword |-> "weaponcrafting", blade |-> "weaponcrafting", iron |-> "none",
                ring |-> "jewelry", loop |-> "jewelry" ]
CraftLevel == [ sword |-> 15, blade |-> 8, iron |-> 0, ring |-> 20, loop |-> 5 ]
Recipe == [ sword |-> {"blade", "iron"}, blade |-> {"iron"}, iron |-> {},
            ring |-> {"loop"}, loop |-> {"ring"} ]

N == Cardinality(Items)
Expand(S) == S \cup UNION { Recipe[m] : m \in S }
Sat[k \in 0..N, r \in Items] == IF k = 0 THEN {r} ELSE Expand(Sat[k-1, r])
Closure(r) == Sat[N, r]

UnmetItems(item, skills) ==
  { m \in Closure(item) : CraftSkill[m] # "none" /\ CraftLevel[m] > skills[CraftSkill[m]] }

WorstRequired(item, skills) ==
  LET U == UnmetItems(item, skills) IN
  IF U = {} THEN 0
  ELSE CHOOSE v \in { CraftLevel[m] : m \in U } : \A m \in U : v >= CraftLevel[m]

MonsterReq(monLevel, charLevel) == monLevel > 0 /\ monLevel > charLevel + MonsterMargin

\* INDEPENDENT oracle: recompute the max unmet CraftLevel directly (inline the unmet
\* predicate; do NOT call UnmetItems/WorstRequired here).
OracleWorst(item, skills) ==
  LET lv == { CraftLevel[m] : m \in { x \in Closure(item) :
                CraftSkill[x] # "none" /\ CraftLevel[x] > skills[CraftSkill[x]] } }
  IN IF lv = {} THEN 0 ELSE CHOOSE v \in lv : \A x \in lv : v >= x

ItemCorrect(item, skills) ==
  /\ WorstRequired(item, skills) = OracleWorst(item, skills)
  /\ (WorstRequired(item, skills) = 0 <=> UnmetItems(item, skills) = {})
  /\ (WorstRequired(item, skills) > 0 =>
        \E m \in Closure(item) : CraftSkill[m] # "none"
           /\ CraftLevel[m] = WorstRequired(item, skills)
           /\ CraftLevel[m] > skills[CraftSkill[m]])

SkillVecs == {
  [weaponcrafting |-> 0,  jewelry |-> 0],
  [weaponcrafting |-> 10, jewelry |-> 0],
  [weaponcrafting |-> 20, jewelry |-> 25],
  [weaponcrafting |-> 0,  jewelry |-> 6]
}
ItemCases == { [item |-> i, skills |-> sv] : i \in Items, sv \in SkillVecs }

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
