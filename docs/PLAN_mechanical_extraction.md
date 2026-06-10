# PLAN: mechanical extraction of Lean models from Python pure-cores

Decision (2026-06-10): Lean models must be MECHANICALLY EXTRACTED from the Python pure-core
decision modules instead of hand-written. Python remains the application; Lean supports it with
proofs. This closes the model-fidelity gap (the CombatTargetExistence false-theorem class): the
generated definition IS a mechanical image of the code, and drift breaks the gate.

## Architecture

- **Extractor**: `scripts/extract_lean.py` — AST-level transpiler for a restricted, typed,
  pure Python subset → Lean 4 definitions. The extractor is the new (small, auditable) trusted
  component; the existing diff oracles remain as a sampling cross-check on it.
- **Generated output**: `formal/Formal/Extracted/<Core>.lean`, header `-- GENERATED from
  <src path> (sha256 …) — DO NOT EDIT`, imported by Formal.lean.
- **Bridge lemmas** (hand-written): `formal/Formal/Extracted/<Core>Bridge.lean` proving
  `Extracted.f = HandModel.f` (definitional / funext+decide / simp). Existing hand theorems then
  transfer; Python drift ⇒ regenerated def changes ⇒ bridge proof breaks ⇒ gate red.
- **Gate**: `formal/gate/check_extraction.sh` — re-runs the extractor, `git diff --exit-code` on
  Formal/Extracted/ (regeneration must be a no-op), then `lake build` proves the bridges. Wired
  into gate.sh and the formal-gate CI workflow.

## Type/construct mapping (v1 subset, from the 2026-06-10 survey)

int→Int (// → Int.fdiv, % → Int.fmod: floor semantics match Python), bool→Bool, str→String,
None/Optional→Option, tuple→Prod, list/Sequence→List, dict/Mapping→List (k × v) + lookup helper,
frozenset/set→List with set-semantics caveat (only order-independent uses allowed: the extractor
REJECTS iteration whose result depends on order unless reduced through max/min with a total key),
Callable→function argument (higher-order). Constructs: if/elif/else, for-with-accumulator,
early return, comparisons, and/or/not, + - * // %, max/min(key=), abs, len, dict.get,
lambda, tuple construction/unpacking. REJECTED in v1: while, try, classes, comprehensions,
generators, float, string methods, recursion (v2), match.

## Migration ladder (easiest → hardest, from survey)

| Tier | Core | Notes |
|---|---|---|
| 1 | combat_picker | 2-pass scan, higher-order predicates — hand model pickWinnableWindowed exists |
| 1 | nearest_tile | min + lex key — hand model NearestTile.lean exists |
| 1 | npc_buy_core | guards + dict update — hand model exists |
| 2 | arbiter_select, priority_band (needs Rat/Fraction), shopping_list (needs recursion) |
| 3 | cycles_for_progress_core, scalar_core (float — extraction-hostile; needs Fraction-typed refactor first or stays sampled) |
| 4 | recipe_closure, inventory_caps, task_batch, task_reservation (GameData reads — need a plain-data facade refactor of the core first) |

## Phases

- **P1 (this session)**: extractor v1 + Tier-1 trio extracted + bridge lemmas + gate wiring.
- **P2**: Tier-2 (adds Fraction→Rat, recursion-with-decreasing-fuel, dataclass→structure).
- **P3**: Tier-3/4 — requires refactors in src (float→Fraction in cores; GameData reads hoisted
  to plain-data params), done per-core with full gates.
- **Policy** (standing, in memory): every NEW pure core ships with an extracted model from day one.

## Session log
- 2026-06-10: plan created; survey complete; P1 build launched.
- 2026-06-10: **P1 COMPLETE.** `scripts/extract_lean.py` shipped (v1 subset per the
  mapping table; loud rejection of out-of-subset constructs with construct + line;
  deterministic byte-identical regeneration; `--check` drift mode). Tier-1 trio
  extracted: `Formal/Extracted/{CombatPicker,NearestTile,NpcBuyCore}.lean`. Bridges
  proved in `Formal/Extracted/Bridges.lean` (no sorry/axioms): `nearest_tile_bridge`
  (pointwise), `combat_picker_bridge` (`extracted ∘ encode = encode ∘ hand` over the
  `Int→String` code embedding, all predicate oracles), `npc_buy_apply_delta`/`_bridge`
  (sumValues encoding), `npc_buy_is_applicable_bridge` (pointwise under `used ≤ cap`).
  HONEST FINDING: Python and the hand `Formal.NpcBuyInventory.isApplicable` genuinely
  diverge OUTSIDE wellformedness — `used > cap ∧ quantity = 0` (Python's negative
  `free` refuses; the hand model's Nat truncation accepts) — kernel-pinned as
  `npc_buy_is_applicable_divergence_outside_wf`, bridge carries `hwf` like every
  existing NpcBuyInventory contract. One src refactor: `nearest_tile.py`
  `if not tiles:` → `if len(tiles) == 0:` (behavior-identical, tests green, mutation
  anchors unaffected). Gate wired: `gate/check_extraction.sh`, gate.sh part (b'''),
  formal-gate.yml step after Role manifest, Formal.lean imports, Manifest #check
  block, Audit #print axioms. P2 next: arbiter_select / priority_band (Rat) /
  shopping_list (fuel recursion).
- 2026-06-10: **P2a COMPLETE** (priority_band + shopping_list; arbiter_select is a
  separate later task). Extractor extensions (now v2): `Fraction` → `Rat`
  (annotation, `+`, two-arg `min`/`max` — the constructs priority_band actually
  uses); FUEL-BOUNDED recursion (leading `fuel: int` param + mandatory
  `if fuel <= 0: return <base>` guard + every self-call passes `fuel - 1` →
  emitted as a two-arm `Nat` pattern match `| 0` / `| fuel + 1`, so Lean
  recursion is STRUCTURAL on the fuel — the hand models' idiom; external Int
  fuel bridged by `Int.toNat`); calls to previously-extracted module functions
  (registry `functions` order = emission order); value-POLYMORPHIC dict helpers
  `_dictGetD`/`_dictSet` (`{α : Type}`; NpcBuyCore.lean regenerated, P1 bridges
  re-proved unchanged); `{}` literals where the dict type is pinned;
  `for k, v in d.items():` loops; set comprehension
  `{elt for k, v in d.items() if cond}` → `List.map ∘ List.filter`.
  SRC REFACTOR (behavior-identical, diff suites + 3081 tests green):
  `_expand` now threads an explicit `(owned, net)` state tuple and a fuel that
  `shopping_list` seeds with `len(recipes) + 1` (unreachable on acyclic
  recipes — proof: any expansion path visits distinct craftables; a cyclic
  recipe now terminates instead of RecursionError, covered by a new test);
  `have` renamed `held` (Lean keyword); `recipes.get(item) or {}` →
  `recipes.get(item, {})` + `len(recipe) == 0`. mutate.py re-anchored (4
  shopping_list mutations, same semantic intent; priority_band anchors
  untouched), verified to match + parse.
  BRIDGES (Extracted/Bridges.lean, no sorry/admit/new axioms):
  `priority_band_bridge` is `rfl` (extracted = hand term-for-term over `Rat`)
  + `priority_band_below_survival` transfers THE survival theorem.
  shopping_list bridge is HONESTLY PARTIAL: the hand model credits a CONSTANT
  `owned` function per node while Python consumes a THREADED dict — equal on
  tree recipes (the differential domain by generator construction), genuinely
  DIVERGENT on DAGs (double-credit vs consume), so a universal
  `extracted = hand` is false, not hard. Proved universally:
  `shopping_raw_node_bridge` (per-node credit/record = hand `deficit`, the
  `Nat.sub` quantity all hand obligations reduce to),
  `shopping_covered_short_circuit_bridge` (covered ⇒ `[(item, 0)]` for EVERY
  recipe env — subtree never expanded) and `shopping_covered_matches_touched`
  (keys = `touched` ∘ encoding via `touched_covered_singleton`). Plus
  clearly-marked WEAKER kernel-checked finite pins (`shopping_pin_*`: raw work
  vs `naiveReq`/`rawReq` at 60/20/0, keys vs `touched`, withdraw set) chosen so
  every registered mutate.py shopping_list mutation flips a pinned value.
  Remaining gap (full net ↔ `rawReq`/`touched` on the tree domain) needs a
  formalized visited-once invariant — deferred; the 300-case differential
  oracle covers it. Proof note: the hand `rawReq`/`touched` mutuals are
  WF-compiled (kernel-irreducible), so pins evaluate the hand side by simp on
  its equations (`show .. (2+1) ..`) and `decide` the extracted side.
  Wired: Formal.lean imports, Manifest #check block, Audit #print axioms;
  check_extraction.sh covers the 5 modules automatically. All gates green:
  `--check` byte-identical ×5, lake build + oracle, no-sorry, axiom gate,
  pytest 3081/100%, mypy strict (src + extractor), ruff.
- 2026-06-10: **P2b COMPLETE** (arbiter_select — THE most-pinned decision
  function: objective-committed arbitration, worth suppression, sticky
  preemption). Extractor extensions (now v3): registry-declared OPAQUE type
  parameters (`Goal`/`Action` → implicit `{X : Type}` binders; payload only);
  frozen `@dataclass` → Lean `structure` (parameterised by the opaque types
  its fields mention; field reads → projections); `next((x for x in xs if
  c), None)` → emitted `_find`; `next((i for i, x in enumerate(xs) if c),
  None)` → `_findIdxFrom`/`_findIdx` (Int index); list comprehension →
  `List.map`∘`List.filter`; `any(e for x in xs)` → `List.any`; FIRST-MATCH
  for loops (body paths only `continue`/`return`, verified no cross-iteration
  state and no post-loop reads of loop locals) → emitted `_findSome` with
  `return e` ↦ `some e`; Optional-guard patterns `if X is None or Y is None:
  <exit>` (nested double-unwrap) and `if X is not None and COND:`; non-exiting
  `if X is not None:` and plain fall-through `if` (rest duplicated into both
  arms); bare reads of non-tuple unwraps resolve to the match binder;
  `==`/`!=` between `Optional[T]` and `T` → `decide (opt = some plain)`;
  `A if c else None` → `if c then some A else none`; componentwise tuple-slot
  return coercion (`T`/None/`[]` into `Optional[T]`/`List` slots). All 5
  prior modules regenerate byte-identically. SRC REFACTOR (behavior-identical,
  arbiter diff suite + tests green): `if plan:` → `if len(plan) > 0:` (2
  sites); mutate.py re-anchored (3 arbiter mutations, same semantic intent;
  walk-inversion mutant now `len(plan) == 0`), all 5 anchors verified to
  match exactly once + parse. BRIDGE (Extracted/Bridges2.lean — new file,
  size split; same `Extracted.Bridges` namespace; no sorry/admit/new axioms;
  core-only): `arbiter_select_bridge` is a FULL commuting square — for EVERY
  injective `f : Nat → String`, every candidate list (duplicate ids included),
  every commitment and oracle triple: `extracted ∘ encode = encOut ∘ hand`
  at `Goal := Nat`, `Action := Unit` (plan `[()]` iff plannable). NO
  wellformedness precondition (both sides are first-match-wins; `idsDisjoint`
  / `guardsFirst` stay hypotheses of the hand safety theorems only) — no
  weaker pins needed. `select_pure_guard_wins_extracted` transfers THE
  sticky-safety theorem to the extracted def. Proof technique: matcher
  auxiliaries never unify across definitions (defeq `rfl` restatements FAIL
  on stuck matches — measured), so the proof drives every match to a
  constructor: `simp only [select_pure]` exposes the generated term, `rw`
  bridges each engine subterm (`_findIdxFrom`/`_find`/`any∘map∘filter`/
  `_findSome` ↦ `indexOf?`/`findCommitted`/`guardPrecedes`/`walk` via a
  `@[reducible]` `eWalkBody` the rewriter can match), then exhaustive
  Bool/Option cases + leaf `simp`. Wired: Formal.lean imports
  (Extracted.ArbiterSelect + Extracted.Bridges2), Manifest #check block,
  Audit #print axioms; check_extraction.sh covers the 6th module
  automatically. P2 closed; next: P3 (float→Fraction refactors, GameData
  facades).
- 2026-06-10: **P2c COMPLETE** — ShoppingList hand model aligned to consume
  semantics; DAG divergence closed. The P2a model-fidelity finding (hand model
  credited a CONSTANT `owned` function per node; Python `_expand` THREADS and
  CONSUMES the owned dict; equal on trees, hand DOUBLE-CREDITS shared stock on
  DAG recipes — the shape real gear recipes have) is fixed by rewriting
  `Formal/ShoppingList.lean` to the threaded `(owned, net)` consume semantics
  on the SHARED extracted encoding (String items, Int quantities,
  insertion-ordered assoc-list dicts `getD`/`setD`; fuel-structural recursion
  seeded `len(recipes)+1`). Python untouched — it is the spec.
  THEOREM LEDGER (nothing became false; every graph-level obligation
  re-proved under consume semantics):
  - kept unchanged: `deficit` + `credit_plus_deficit` / `deficit_le_qty` /
    `deficit_antitone` / `deficit_zero_iff_covered` (per-node Nat credit).
  - re-proved (renamed, consume semantics): `rawReq_le_naive` →
    `shoppingList_raw_le_naive`; `rawReq_antitone_owned` →
    `shoppingList_raw_antitone_owned`; `rawReq_mono_qty` →
    `shoppingList_raw_mono_qty`; `naiveReq_raw` →
    `shoppingList_raw_no_holdings`; `touched_covered_singleton` →
    `shoppingList_covered_singleton` (+ `fullyCovered_covered_singleton`).
    All three monotonicity/dominance results follow from ONE simulation
    lemma `work_mono` (pointwise-≤ holdings + ≤ quantity ⇒ ≤ work, holdings
    stay pointwise-ordered and non-negative; hypotheses `RecipesNonneg`,
    `OwnedNonneg` — production invariants) plus the graph-level
    RECONSTRUCTION `expand_eq_work`/`shoppingList_eq_work` (net raw-leaf
    total = threaded `work`). New DAG witness `example` pins the consume
    accounting (2 shared ore credited once, not twice).
  - dropped defs: `rawReq`/`sumReq`/`naiveReq`/`touched`/`touchedSubs`
    (the unfaithful constant-credit recursion — superseded, not falsified).
  FULL BRIDGE (Bridges.lean): `shopping_expand_bridge` proves extracted
  `_expand` = hand `expand` for ALL fuels/items/quantities/recipes/states
  (induction on fuel; `simp only` with `_dictGetD/_dictSet = getD/setD` and
  the fuel IH closes the generated term); `shopping_list_bridge` /
  `shopping_fully_covered_bridge` give the API equalities — UNIVERSAL, DAGs
  included. Kept: `shopping_raw_node_bridge` (per-node credit = `deficit`)
  and `shopping_covered_short_circuit_bridge` (now derived from the universal
  bridge). Deleted: `shopping_covered_matches_touched` + the 5 weaker
  `shopping_pin_*` (each a finite instance of the universal statement).
  ORACLE: `runShoppingList` now runs the proved `shoppingList` (consume) with
  Python's own fuel seeding; same `{raw_work, keys}` output shape; the unused
  `fuel` wire arg dropped (args builder lives in the diff test).
  DIFFERENTIAL: generator upgraded trees → DAGs (a child may be claimed by
  multiple parents) — tree-only generation is what masked the divergence;
  pinned: `test_dag_double_credit_witness` (raw work 2 consume vs 0
  constant-credit), `test_dag_diamond_one_path_covered` (1 vs 0),
  `test_partial_bank_partial_credit` (deterministic kill for the
  `used = 0` / `qty + used` / `per_unit * qty` mutants; short-circuit mutant
  killed by the keys pin). All 4 mutate.py shopping_list anchors verified to
  match source.
  FOLLOW-UP (out of P2c scope, flagged in StepDispatch.lean): `min_gathers.py`
  also consumes a threaded copy while the `Formal.StepDispatch.minGathers`
  hand model credits a constant `owned` per node — the SAME tree-only-domain
  gap; align it the same way (its differential generator also builds trees).
  Gates green: lake build + oracle, no-sorry, axiom gate (core safety
  namespaces clean), extraction `--check` byte-identical ×6, proof-concept
  index, orphan modules, shopping_list + recipe_closure + gather_selection
  diff suites, full pytest 100%, mypy strict, ruff.
