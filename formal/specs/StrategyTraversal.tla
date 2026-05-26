----------------------------- MODULE StrategyTraversal -----------------------------
\* Mirrors src/artifactsmmo_cli/ai/tiers/strategy.py: is_reachable:125, unmet_closure_size:91, actionable_step:69, root_cost:107
EXTENDS Integers, FiniteSets, TLC
Max(a, b) == IF a > b THEN a ELSE b

Nodes == {"g_char", "g_skill", "g_sword", "g_blade", "g_iron", "g_ringA", "g_ringB"}
Kind == [ g_char |-> "char", g_skill |-> "skill", g_sword |-> "obtain", g_blade |-> "obtain",
          g_iron |-> "obtain", g_ringA |-> "obtain", g_ringB |-> "obtain" ]
Prereqs == [ g_char |-> {}, g_skill |-> {}, g_sword |-> {"g_blade"}, g_blade |-> {"g_iron"},
             g_iron |-> {}, g_ringA |-> {"g_ringB"}, g_ringB |-> {"g_ringA"} ]  \* g_sword->g_blade->g_iron chain; g_ringA<->g_ringB cycle (tests cycle-safety)
IsSat == [ g_char |-> FALSE, g_skill |-> FALSE, g_sword |-> FALSE, g_blade |-> FALSE,
           g_iron |-> FALSE, g_ringA |-> FALSE, g_ringB |-> FALSE ]
Producible == [ g_char |-> TRUE, g_skill |-> TRUE, g_sword |-> TRUE, g_blade |-> TRUE,
                g_iron |-> TRUE, g_ringA |-> FALSE, g_ringB |-> FALSE ]  \* g_iron is a producible leaf; the cyclic ring nodes are not producible
NN == Cardinality(Nodes)

\* is_reachable (algorithm model): cycle-safe via path subset
Reach[n \in Nodes, p \in SUBSET Nodes] ==
  IF IsSat[n] THEN TRUE
  ELSE IF n \in p THEN FALSE
  ELSE IF Kind[n] = "skill" THEN TRUE
  ELSE IF Kind[n] = "obtain" /\ Prereqs[n] = {} THEN Producible[n]
  ELSE \A q \in Prereqs[n] : Reach[q, p \cup {n}]
IsReachable(n) == Reach[n, {}]

\* INDEPENDENT oracle: well-founded grounding fixpoint
GroundStep(G) == { n \in Nodes :
                     \/ IsSat[n]
                     \/ Kind[n] = "skill"
                     \/ (Kind[n] = "obtain" /\ Prereqs[n] = {} /\ Producible[n])
                     \* char/skill (empty prereqs) ground vacuously via \A over {}; non-leaf obtain grounds when all prereqs in G; leaf-obtain handled by the producible disjunct above
                     \/ (~(Kind[n] = "obtain" /\ Prereqs[n] = {}) /\ \A q \in Prereqs[n] : q \in G) }
Gnd[k \in 0..NN] == IF k = 0 THEN {} ELSE GroundStep(Gnd[k-1])
\* Two independent reachability formulations are intentional — do NOT unify.
\* Reach = algorithm model (path-recursive, cycle-safe). Grounded = oracle (monotone
\* fixpoint). ReachCorrect cross-checks they agree; merging defeats the check.
Grounded == Gnd[NN]
ReachCorrect(n) == IsReachable(n) = (n \in Grounded)

\* unmet_closure_size: |unmet in prereq closure|, min 1
Clo[k \in 0..NN, r \in Nodes] == IF k = 0 THEN {r} ELSE Clo[k-1, r] \cup UNION { Prereqs[m] : m \in Clo[k-1, r] }
ClosureOf(r) == Clo[NN, r]
SizeModel(r) == Max(Cardinality({ m \in ClosureOf(r) : ~IsSat[m] }), 1)
\* INDEPENDENT oracle: count via (closure size - satisfied count), floored 1 — different expression.
SizeOracle(r) == Max(Cardinality(ClosureOf(r)) - Cardinality({ m \in ClosureOf(r) : IsSat[m] }), 1)
SizeCorrect(r) == SizeModel(r) = SizeOracle(r)

\* actionable_step: a node reachable from root, unmet, all DIRECT prereqs satisfied,
\* (obtain => producible). Model the SET; the function returns one (DFS order picks which).
Actionables(r) == { m \in ClosureOf(r) :
                      ~IsSat[m] /\ (\A q \in Prereqs[m] : IsSat[q]) /\ (Kind[m] = "obtain" => Producible[m]) }
\* Independent (De Morgan) re-derivation of the actionable frontier: a node is
\* actionable iff unmet, has NO unmet direct prereq, and is producible-if-obtain.
ActionablesOracle(r) == { m \in ClosureOf(r) :
                            ~IsSat[m]
                            /\ ~ (\E q \in Prereqs[m] : ~IsSat[q])
                            /\ (Kind[m] = "obtain" => Producible[m]) }
StepCorrect(r) ==
  /\ Actionables(r) = ActionablesOracle(r)        \* model frontier = independent De Morgan oracle
  /\ (Actionables(r) = {} <=> ActionablesOracle(r) = {})  \* None iff no actionable node (cyclic/blocked)
  \* concrete fixture expectations (cyclic ring is blocked; sword chain bottoms out at the iron leaf):
  /\ (r = "g_ringA" => Actionables(r) = {})
  /\ (r = "g_sword" => Actionables(r) = {"g_iron"})

\* root_cost: char/skill = max(1, level diff); gear(obtain) = unmet_closure_size
RootCost(r, charLvl, charTarget, skillLvl, skillTarget) ==
  IF Kind[r] = "char" THEN Max(1, charTarget - charLvl)
  ELSE IF Kind[r] = "skill" THEN Max(1, skillTarget - skillLvl)
  ELSE SizeModel(r)
CostCorrect(r) ==
  /\ RootCost(r, 10, 50, 3, 50) >= 1
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
