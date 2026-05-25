----------------------------- MODULE RecipeClosure -----------------------------
EXTENDS Integers, FiniteSets, Sequences, TLC

\* Mirrors src/artifactsmmo_cli/ai/recipe_closure.py:
\*   recipe_closure (DFS with visited guard) and raw_material_units (cyclic-safe
\*   recursive cost). The oracle is an independently-computed least-fixpoint
\*   closure by saturation plus a hand-computed raw-unit table. Includes a CYCLIC
\*   recipe (ring<->loop, a<->b) and a DIAMOND (sword via blade+handle, both
\*   needing iron) to exercise the visited guard and shared-subrecipe handling.

Items == {"sword", "blade", "iron", "handle", "wood", "ring", "loop", "a", "b"}
Empty == [ x \in {} |-> 0 ]
Recipe ==
  [ sword  |-> [blade |-> 1, handle |-> 1],
    blade  |-> [iron  |-> 2],
    handle |-> [iron  |-> 1, wood |-> 1],
    iron   |-> Empty,
    wood   |-> Empty,
    ring   |-> [loop |-> 2],
    loop   |-> [ring |-> 1],
    a      |-> [b |-> 1],
    b      |-> [a |-> 1] ]
Drops == [ iron_rocks |-> "iron", ash_tree |-> "wood" ]
Resources == DOMAIN Drops
HasRecipe(m) == m \in DOMAIN Recipe /\ DOMAIN Recipe[m] # {}

N == Cardinality(Items)

\* ---- a deterministic sequence of a set's elements (no RECURSIVE operator) ----
\* SetSeq[T] picks an arbitrary element, prepends it, and recurses on the rest.
\* Used to fold a sum over a recipe's ingredient set without a built-in set sum.
SetSeq[T \in SUBSET Items] ==
  IF T = {} THEN << >>
  ELSE LET e == CHOOSE x \in T : TRUE
       IN Append(SetSeq[T \ {e}], e)

\* ============================================================================
\* ORACLE: least-fixpoint closure by saturation (independent of the DFS).
\* Each round Expand adds every ingredient of every craftable item in the set.
\* The closure stabilizes within N = |Items| rounds (each round before the
\* fixpoint adds >= 1 new item, and there are only N items total).
\* Keyed by both round k and the root r so it is defined for every item.
\* ============================================================================
Expand(S) == S \cup UNION { DOMAIN Recipe[m] : m \in { x \in S : HasRecipe(x) } }
Sat[k \in 0..N, r \in Items] ==
  IF k = 0 THEN {r} ELSE Expand(Sat[k - 1, r])
ClosureSet(item) == Sat[N, item]

OracleCraftable(item) == { m \in ClosureSet(item) : HasRecipe(m) }
OracleResources(item) == { r \in Resources : Drops[r] \in ClosureSet(item) }

\* ============================================================================
\* ALGORITHM MODEL: recipe_closure's DFS with a visited guard.
\* AlgoClosure is the set of all materials reachable from the root following
\* recipe ingredients, with the visited guard preventing infinite descent on
\* cyclic recipes. As a reachability set this is exactly the same set the
\* fixpoint produces; modeled here as its own bounded reachability so the
\* equality AlgoClosure = ClosureSet is a genuine (re-derived) check, not an
\* alias. AReach[k] = items within k ingredient-hops of the root.
\* ============================================================================
AStep(S) == S \cup UNION { DOMAIN Recipe[m] : m \in { x \in S : HasRecipe(x) } }
AReach[k \in 0..N, r \in Items] ==
  IF k = 0 THEN {r} ELSE AStep(AReach[k - 1, r])
AlgoClosure(item) == AReach[N, item]

AlgoCraftable(item) == { m \in AlgoClosure(item) : HasRecipe(m) }
AlgoResources(item) == { r \in Resources : Drops[r] \in AlgoClosure(item) }

\* ============================================================================
\* raw_material_units: recursive cost keyed by (item, visited). Revisit -> 1,
\* raw/unknown -> 1, else sum over ingredients of qty * RU[sub, visited+item].
\* The visited set strictly grows on each descent (bounded by Items), so the
\* recursion terminates even on cyclic recipes. The per-recipe sum is folded
\* over a deterministic sequence of the ingredient set (SumIngs below): no
\* built-in set sum and no RECURSIVE operator needed.
\* ============================================================================
RU[item \in Items, visited \in SUBSET Items] ==
  IF item \in visited THEN 1
  ELSE IF ~HasRecipe(item) THEN 1
  ELSE LET reci   == Recipe[item]
           deeper == visited \cup {item}
           ings   == SetSeq[DOMAIN reci]
           \* fold qty(ing) * RU[ing, deeper] over the ingredient sequence
           Sum[i \in 0..Len(ings)] ==
             IF i = 0 THEN 0
             ELSE Sum[i - 1] + reci[ings[i]] * RU[ings[i], deeper]
       IN Sum[Len(ings)]
RawUnits(item) == RU[item, {}]

\* hand-computed oracle table. Each value is the cost with the item AS ROOT
\* (visited = {}), matching raw_material_units' public entry point.
\* sword: blade(iron*2)=2 + handle(iron*1 + wood*1)=2  => 4   (diamond, shares iron)
\* ring : loop * 2; loop=ring*1 with ring now visited => loop=1, so ring=2*1=2
\* loop : ring * 1; ring=loop*2 with loop now visited => loop=1, so ring=2, loop=1*2=2
\* a    : b*1; b=a*1 with a visited => b=1, so a=1
\* b    : a*1; a=b*1 with b visited => a=1, so b=1
\* (ring=loop=2 are symmetric as roots; the plan's "loop=1" was loop's value as a
\*  SUBrecipe of an already-visited ring, not as a root. Verified against the
\*  Python recipe_closure.raw_material_units, which is the unit under test.)
ExpectedRaw == [ sword |-> 4, blade |-> 2, handle |-> 2, iron |-> 1,
                 wood |-> 1, ring |-> 2, loop |-> 2, a |-> 1, b |-> 1 ]

Correct(item) ==
  /\ AlgoClosure(item)   = ClosureSet(item)
  /\ AlgoCraftable(item) = OracleCraftable(item)
  /\ AlgoResources(item) = OracleResources(item)
  /\ RawUnits(item)      = ExpectedRaw[item]

VARIABLE todo
Init == todo = Items
Next == /\ todo # {}
        /\ \E m \in todo :
              /\ Assert(Correct(m), <<"RecipeClosure FAIL", m>>)
              /\ todo' = todo \ {m}
================================================================================
