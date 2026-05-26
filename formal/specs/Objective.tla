------------------------------- MODULE Objective -------------------------------
EXTENDS Integers, FiniteSets, TLC

\* Mirrors src/artifactsmmo_cli/ai/tiers/objective.py:
\*   is_attainable (:15) -- a craft chain is attainable iff it bottoms out in
\*     resource-drops (gatherables) with no drop-only/unknown component; cycle->FALSE.
\*   from_game_data (:57) -- best-equip-value attainable item per slot/type (argmax,
\*     ties by code ascending), matching sorted(key=(-value, code)) + attainable filter.
\*   gap (:86) -- per-axis non-negative gaps; is_complete iff every fraction is 0.
\* equip_value (tiers/equip_value.py) is modeled as one integer per item.
\* Float fractions (objective.py:102-106) are gap/denom; we assert 0 <= gap <= denom
\* (integer), which is equivalent to fraction in [0,1] without computing floats.

Max(a, b) == IF a > b THEN a ELSE b

Items == {"none", "wood_sword", "iron_sword", "gem_sword", "iron", "wood", "gem"}
HasRecipe == [ none |-> FALSE, wood_sword |-> TRUE, iron_sword |-> TRUE, gem_sword |-> TRUE,
               iron |-> FALSE, wood |-> FALSE, gem |-> FALSE ]
Recipe == [ none |-> {}, wood_sword |-> {"wood"}, iron_sword |-> {"iron"},
            gem_sword |-> {"gem"}, iron |-> {}, wood |-> {}, gem |-> {} ]
\* gem: IsDrop=FALSE (drop-only, not gatherable) => gem_sword is NOT attainable. Pivotal test case.
IsDrop == [ none |-> FALSE, wood_sword |-> FALSE, iron_sword |-> FALSE, gem_sword |-> FALSE,
            iron |-> TRUE, wood |-> TRUE, gem |-> FALSE ]
EquipValue == [ none |-> 0, wood_sword |-> 10, iron_sword |-> 25, gem_sword |-> 40,
                iron |-> 0, wood |-> 0, gem |-> 0 ]
ItemType == [ none |-> "none", wood_sword |-> "weapon", iron_sword |-> "weapon",
              gem_sword |-> "weapon", iron |-> "none", wood |-> "none", gem |-> "none" ]
Weapons == { c \in Items : ItemType[c] = "weapon" }

\* is_attainable (algorithm model): cycle-safe via path subset
Att[code \in Items, path \in SUBSET Items] ==
  IF HasRecipe[code]
  THEN IF code \in path THEN FALSE ELSE \A m \in Recipe[code] : Att[m, path \cup {code}]
  ELSE IsDrop[code]
IsAttainable(code) == Att[code, {}]

\* Do NOT unify Att and Grounded: independence IS the cross-check. Att is the
\* path-recursive algorithm model; Grounded is a monotone least-fixpoint oracle.
\* They must agree (AttainCorrect) yet be structurally distinct — merging defeats it.
\* independent oracle: least-fixpoint grounding
N == Cardinality(Items)
GroundStep(G) == { c \in Items : IF HasRecipe[c] THEN \A m \in Recipe[c] : m \in G ELSE IsDrop[c] }
Gnd[k \in 0..N] == IF k = 0 THEN {} ELSE GroundStep(Gnd[k-1])
Grounded == Gnd[N]
AttainCorrect(code) == IsAttainable(code) = (code \in Grounded)

\* best-attainable gear per type (argmax equip_value over attainable, ties code asc)
AttainableWeapons == { c \in Weapons : IsAttainable(c) }
BestWeapon == IF AttainableWeapons = {} THEN "none"
  ELSE CHOOSE b \in AttainableWeapons :
         \A o \in AttainableWeapons : EquipValue[b] > EquipValue[o] \/ (EquipValue[b] = EquipValue[o] /\ b <= o)
GearCorrect == /\ BestWeapon = "iron_sword"
               /\ (AttainableWeapons # {} => \A o \in AttainableWeapons : EquipValue[BestWeapon] >= EquipValue[o])

\* gap structure (integer; fractions verified as 0 <= gap <= denom)
TargetLevel == 50
MaxSkill == 50
Skills == {"mining", "cooking"}
GapState == { [lvl |-> l, sk |-> s, gearDef |-> g] :
                l \in {0, 25, 50}, s \in [Skills -> {0, 50}], g \in {0, 5, 40} }
CharGap(st) == Max(0, TargetLevel - st.lvl)
SkillGap(st, sk) == Max(0, MaxSkill - st.sk[sk])
\* hardcoded to the two-skill fixture (mining, cooking); keep in sync with Skills if extended
SkillGapSum(st) == SkillGap(st, "mining") + SkillGap(st, "cooking")
SkillsDenom == Cardinality(Skills) * MaxSkill
IsComplete(st) == CharGap(st) = 0 /\ SkillGapSum(st) = 0 /\ st.gearDef = 0
GapCorrect(st) ==
  /\ CharGap(st) >= 0 /\ CharGap(st) <= TargetLevel
  /\ SkillGapSum(st) >= 0 /\ SkillGapSum(st) <= SkillsDenom
  /\ st.gearDef >= 0
  \* Independent characterization: completeness in terms of the RAW state hitting
  \* targets (lvl=Target, each skill=MaxSkill, no gear deficit), NOT a restatement
  \* of IsComplete's own Gap-operator body -- so this conjunct genuinely bites.
  /\ (IsComplete(st) <=> (st.lvl = TargetLevel /\ st.sk["mining"] = MaxSkill
                          /\ st.sk["cooking"] = MaxSkill /\ st.gearDef = 0))

Tagged == { [kind |-> "att", v |-> c] : c \in Items }
            \cup { [kind |-> "gear", v |-> "x"] }
            \cup { [kind |-> "gap", v |-> st] : st \in GapState }
Check(t) == IF t.kind = "att" THEN AttainCorrect(t.v)
            ELSE IF t.kind = "gear" THEN GearCorrect ELSE GapCorrect(t.v)

VARIABLE todo
Init == todo = Tagged
Next == /\ todo # {}
        /\ \E t \in todo :
              /\ Assert(Check(t), <<"Objective FAIL", t>>)
              /\ todo' = todo \ {t}
================================================================================
