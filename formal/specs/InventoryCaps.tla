------------------------------- MODULE InventoryCaps -------------------------------
EXTENDS Integers, FiniteSets, TLC

\* Mirrors src/artifactsmmo_cli/ai/inventory_caps.py:30,82.
\* cap = max(recipe_cap, task_cap, action_cap, equippable_cap), where recipe_cap
\* is floored to SafetyFloor only when recipe demand > 0; equipped items get a
\* floor of max(1, cap). overstocked_items keeps {code |-> qty - cap} for every
\* held item whose qty > 0 and qty > cap. Item attributes and state are small
\* enumerated tables.

BatchBuffer == 5
SafetyFloor == 3
EquipKeep   == 1
CoinCap     == 9  \* ACTION_CONSUMABLES_CAP["tasks_coin"] (inventory_caps.py:25-27)

Max(a, b) == IF a > b THEN a ELSE b

Items == {"coin", "ore", "sword", "potion", "junk"}
RecipeDemand == [ coin |-> 0, ore |-> 6, sword |-> 0, potion |-> 0, junk |-> 0 ]
Equippable   == [ coin |-> FALSE, ore |-> FALSE, sword |-> TRUE, potion |-> FALSE, junk |-> FALSE ]
ActionCap    == [ coin |-> CoinCap, ore |-> 0, sword |-> 0, potion |-> 0, junk |-> 0 ]

RecipeCap(code) ==
  LET rmax == RecipeDemand[code] IN
  IF rmax > 0 THEN Max(rmax * BatchBuffer, SafetyFloor) ELSE 0

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

\* Independent oracle — intentionally NOT refactored to call Cap/CapExclEquipped.
\* Both must compute the same result by different expression paths so CapCorrect
\* has real verification power (not a tautology). Do NOT DRY these together.
OracleCap(code, taskItem, remaining, equipped) ==
  LET base == IF RecipeDemand[code] > 0 THEN Max(RecipeDemand[code] * BatchBuffer, SafetyFloor) ELSE 0
      t    == IF code = taskItem THEN remaining ELSE 0
      a    == ActionCap[code]
      e    == IF Equippable[code] THEN EquipKeep ELSE 0
      m    == Max(Max(base, t), Max(a, e))
  IN IF code \in equipped THEN Max(1, m) ELSE m

TaskItems == Items \cup {"none"}
Remains   == 0..3  \* task-remaining range; spans the SafetyFloor=3 boundary
EquipSets == SUBSET {"sword", "ore"}  \* includes "ore" (not equippable) to test the equipped-but-not-equippable edge: cap still >= 1

CapCases == { [code |-> code, ti |-> ti, rem |-> rem, eq |-> eq] :
                code \in Items, ti \in TaskItems, rem \in Remains, eq \in EquipSets }

CapCorrect(c) ==
  /\ Cap(c.code, c.ti, c.rem, c.eq) = OracleCap(c.code, c.ti, c.rem, c.eq)
  /\ (c.code \in c.eq => Cap(c.code, c.ti, c.rem, c.eq) >= 1)

Overstock(inv, taskItem, remaining, equipped) ==
  [ code \in { c \in DOMAIN inv : inv[c] > 0 /\ inv[c] > Cap(c, taskItem, remaining, equipped) }
        |-> inv[code] - Cap(code, taskItem, remaining, equipped) ]

OverCases == {
  [inv |-> [ore |-> 40, junk |-> 2, coin |-> 12], ti |-> "none", rem |-> 0, eq |-> {},
   exp |-> [ore |-> 10, junk |-> 2, coin |-> 3]],
  [inv |-> [sword |-> 3], ti |-> "none", rem |-> 0, eq |-> {},
   exp |-> [sword |-> 2]],
  [inv |-> [sword |-> 3], ti |-> "none", rem |-> 0, eq |-> {"sword"},
   exp |-> [sword |-> 2]],
  [inv |-> [ore |-> 5], ti |-> "none", rem |-> 0, eq |-> {},
   exp |-> [c \in {} |-> 0]]  \* ore cap=30, 5<=30 => not overstocked; empty map is the expected result
}
OverCorrect(c) == Overstock(c.inv, c.ti, c.rem, c.eq) = c.exp

\* Tagged union so one VARIABLE/Next drives both the cap and overstock case sets.
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
