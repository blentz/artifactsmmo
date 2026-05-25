--------------------------- MODULE PrerequisiteGraph ---------------------------
EXTENDS Integers, FiniteSets, TLC

\* Mirrors src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py:
\*   prerequisites (:41) -- direct prereqs of an ObtainItem node, and
\*   combat_capable (:20) -- any(predict_win) over reachable monsters.
\* Verifies (1) emitted direct edges are exact, (2) leaf classification is exact
\* (gather/monster-drop/buyable terminate the chain), (3) expansion from each
\* node reaches only recipe-or-leaf nodes (search terminates), and (4) the
\* combat gate equivalence combat_capable <=> \E monster beatable, checked over
\* all verdict combinations. The per-monster predict_win refinement is in
\* PredictWin.tla; here the `any` aggregation is what is verified.

Items == {"sword", "blade", "iron", "wood", "gem"}
\* Empty recipe domain: safe sentinel so DOMAIN Recipe[m] is total over leaf items.
Empty == [ x \in {} |-> 0 ]
Recipe ==
  [ sword |-> [blade |-> 1],
    blade |-> [iron  |-> 2],
    iron  |-> Empty,     \* gathered (has a resource drop)
    wood  |-> Empty,     \* gathered
    gem   |-> Empty ]    \* monster-drop / buyable: leaf, no prereqs
Drops == [ iron_rocks |-> "iron", ash_tree |-> "wood" ]
Gatherable == { Drops[r] : r \in DOMAIN Drops }
HasRecipe(m) == m \in DOMAIN Recipe /\ DOMAIN Recipe[m] # {}

\* algorithm model: direct prerequisites of an ObtainItem node
\* (skill-level prereqs from crafting_skill/resource_skill_level are abstracted
\*  out; we verify the material/leaf structure that drives search shape.)
Prereqs(node) ==
  IF HasRecipe(node) THEN DOMAIN Recipe[node]   \* craft: ingredients
  ELSE IF node \in Gatherable THEN {}           \* gather: leaf (skill only)
  ELSE {}                                       \* monster-drop/buyable: leaf

\* oracle: hand-specified expected direct prereqs
ExpectedPrereqs ==
  [ sword |-> {"blade"}, blade |-> {"iron"}, iron |-> {}, wood |-> {}, gem |-> {} ]
IsLeaf(node) == Prereqs(node) = {}
ExpectedLeaves == { "iron", "wood", "gem" }

\* oracle: independent reachability fixpoint => termination.
\* Reach is rewritten from the planned RECURSIVE form as a bounded recursive
\* FUNCTION keyed by round k and root r (PlusPy has no RECURSIVE keyword). Each
\* round Expand adds the direct prereqs of every node already in the set; the
\* closure stabilizes within N = |Items| rounds (each round before the fixpoint
\* adds >= 1 new node, and there are only N nodes total).
N == Cardinality(Items)
Expand(S) == S \cup UNION { Prereqs(m) : m \in S }
ReachF[k \in 0..N, r \in Items] ==
  IF k = 0 THEN {r} ELSE Expand(ReachF[k - 1, r])
Reach(root) == ReachF[N, root]

AllReachableTerminate(root) ==
  LET R == Reach(root) IN \A n \in R : (HasRecipe(n) \/ IsLeaf(n))

NodeCorrect(node) ==
  /\ Prereqs(node) = ExpectedPrereqs[node]   \* exact direct edges
  /\ (IsLeaf(node) <=> node \in ExpectedLeaves)
  /\ AllReachableTerminate(node)             \* search terminates

\* combat_capable == any(predict_win(m) for m in monsters). The per-monster
\* predict_win verdict is refined operationally in PredictWin.tla; here we verify
\* the `any` aggregation itself. The verdict is modelled as the SET of beatable
\* monsters, and the existential is checked against an independent cardinality
\* oracle over EVERY possible verdict combination (all 2^|Monsters| subsets) — so
\* both the "some beatable => TRUE" and "none beatable => FALSE" branches bite.
Monsters == {"chicken", "cow", "wolf"}
CombatCapable(beatable) == \E m \in Monsters : m \in beatable
AnyOracle(beatable)     == Cardinality(beatable) > 0
CombatGateCorrect == \A beatable \in SUBSET Monsters :
                       CombatCapable(beatable) = AnyOracle(beatable)

VARIABLE todo
Init == todo = Items
Next == /\ todo # {}
        /\ \E node \in todo :
              /\ Assert(NodeCorrect(node), <<"PrereqGraph FAIL node", node>>)
              /\ Assert(CombatGateCorrect, <<"PrereqGraph FAIL combat gate">>)  \* whole-spec invariant, not node-scoped; re-checked each step harmlessly
              /\ todo' = todo \ {node}
================================================================================
