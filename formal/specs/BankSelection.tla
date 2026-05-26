------------------------------- MODULE BankSelection -------------------------------
EXTENDS Integers, FiniteSets, Sequences, TLC

\* Mirrors src/artifactsmmo_cli/ai/bank_selection.py:
\*   select_bank_deposits, _keep_codes, _recipe_materials, _best_fighting_weapon.
\* The keep-set closure is the documented PursueTask-freeze root cause: banking
\* the active items-task item's recipe inputs starves gather->craft->TaskTrade.
\* Verified over hand-built states incl. one (s3) where a recipe material is the
\* items-task item. The deposit ORDER is the Python stdlib .sort's correctness,
\* not ours; we assert the sort KEY (Key/LE) is a strict total order over the
\* deposit set, so a well-defined sort exists, instead of building a sequence.

TasksCoin == "coin"

Items == {"coin", "iron", "wood", "blade", "sword", "potion", "axe", "stick"}
\* Recipe[m] = direct ingredient codes of m (qty abstracted out; the keep-set
\* closure only needs the material SET, matching _recipe_materials' walk).
Recipe == [ coin |-> {}, iron |-> {}, wood |-> {}, potion |-> {}, stick |-> {},
            blade |-> {"iron"},
            sword |-> {"blade", "stick"},
            axe   |-> {"wood"} ]
HpRestore == [ coin |-> 0, iron |-> 0, wood |-> 0, blade |-> 0, sword |-> 0,
               potion |-> 40, axe |-> 0, stick |-> 0 ]
IsWeapon  == [ coin |-> FALSE, iron |-> FALSE, wood |-> FALSE, blade |-> FALSE,
               sword |-> TRUE, potion |-> FALSE, axe |-> TRUE, stick |-> FALSE ]
IsTool    == [ coin |-> FALSE, iron |-> FALSE, wood |-> FALSE, blade |-> FALSE,
               sword |-> FALSE, potion |-> FALSE, axe |-> TRUE, stick |-> FALSE ]
Attack    == [ coin |-> 0, iron |-> 0, wood |-> 0, blade |-> 0, sword |-> 10,
               potion |-> 0, axe |-> 8, stick |-> 0 ]
SellValue == [ coin |-> 0, iron |-> 5, wood |-> 3, blade |-> 12, sword |-> 50,
               potion |-> 7, axe |-> 20, stick |-> 1 ]

\* ---- _recipe_materials walk as a bounded recursive function (no RECURSIVE) ----
\* The walk EXCLUDES the root: materials accumulate the ingredients of every
\* visited item, but the root r itself is never added unless it is some other
\* item's ingredient. Sat[0,r] = Recipe[r] (root's direct ingredients only),
\* then each round adds the ingredients of items already collected. Stabilizes
\* within N = |Items| rounds (each pre-fixpoint round adds >= 1 new code).
N == Cardinality(Items)
ExpandMats(S) == S \cup UNION { Recipe[m] : m \in S }
Sat[k \in 0..N, r \in Items] == IF k = 0 THEN Recipe[r] ELSE ExpandMats(Sat[k-1, r])
MatsOf(r) == Sat[N, r]
MatsOfRoots(roots) == UNION { MatsOf(r) : r \in roots }

\* _best_fighting_weapon: highest-attack non-tool weapon among inv+equipped, tie
\* broken by code ascending (deterministic); tools excluded (skill_effects).
WeaponCands(inv, equipped) == { c \in (DOMAIN inv \cup equipped) : IsWeapon[c] /\ ~IsTool[c] }
BestWeapon(inv, equipped) ==
  LET cands == WeaponCands(inv, equipped) IN
  IF cands = {} THEN "none"
  ELSE CHOOSE w \in cands :
         \A o \in cands : (Attack[w] > Attack[o]) \/ (Attack[w] = Attack[o] /\ w <= o)

KeepSet(s) ==
  LET base == {TasksCoin}
      withTask == IF s.taskCode # "none" THEN base \cup {s.taskCode} ELSE base
      hp == { c \in DOMAIN s.inv : HpRestore[c] > 0 }
      bw == BestWeapon(s.inv, s.equipped)
      withWeapon == (withTask \cup hp) \cup (IF bw # "none" THEN {bw} ELSE {})
      roots == (IF s.craftingTarget # "none" THEN {s.craftingTarget} ELSE {})
                 \cup (IF s.taskType = "items" /\ s.taskCode # "none" THEN {s.taskCode} ELSE {})
  IN withWeapon \cup MatsOfRoots(roots)

DepositSet(s) == { c \in DOMAIN s.inv : s.inv[c] > 0 /\ c \notin KeepSet(s) }

\* Sort key: (-sell_value, code). LE is the lexicographic <= over the key pairs.
LE(a, b) == (a[1] < b[1]) \/ (a[1] = b[1] /\ a[2] <= b[2])
Key(c) == << -SellValue[c], c >>

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

ExpectedKeep == [
  s1 |-> {"coin", "potion", "sword", "blade", "stick", "iron"},
  s2 |-> {"coin"},
  s3 |-> {"coin", "iron", "potion"} ]
TagOf(s) == IF s.craftingTarget = "sword" THEN "s1"
            ELSE IF s.taskCode = "iron" THEN "s3" ELSE "s2"

Correct(s) ==
  LET keep == KeepSet(s)
      dep  == DepositSet(s)
  IN /\ keep = ExpectedKeep[TagOf(s)]
     /\ dep \cap keep = {}
     /\ dep = { c \in DOMAIN s.inv : s.inv[c] > 0 /\ c \notin keep }
     /\ MatsOfRoots(IF s.taskType = "items" /\ s.taskCode # "none"
                    THEN {s.taskCode} ELSE {}) \subseteq keep
     \* Sort key is a strict total order over the deposit set, so a well-defined
     \* deterministic .sort exists: totality + antisymmetry on distinct codes.
     /\ \A a \in dep, b \in dep : LE(Key(a), Key(b)) \/ LE(Key(b), Key(a))
     /\ \A a \in dep, b \in dep : a # b => Key(a) # Key(b)

VARIABLE todo
Init == todo = States
Next == /\ todo # {}
        /\ \E s \in todo :
              /\ Assert(Correct(s), <<"BankSelection FAIL", TagOf(s)>>)
              /\ todo' = todo \ {s}
================================================================================
