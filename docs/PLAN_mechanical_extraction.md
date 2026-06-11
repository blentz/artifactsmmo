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
- **P4 (the deferred ledger from P1-P3)**:
  - **P4a — equipment-scoring exact-arithmetic migration**: tiers/equip_value.py and its float
    consumers (tiers/objective.py, tiers/strategy.py gains, tiers/prerequisite_graph.py,
    goals/progression.py, goals/upgrade_selection.py) move from float to exact arithmetic
    (int where summands are ints, Fraction where division appears). HONESTY NOTE: float→exact
    in RANKING comparisons may flip near-ties — exact is the spec going forward; behavior is
    NOT byte-identical by definition; diff oracles re-pinned exactly (tolerances removed where
    the model is rational); trace behavior may shift marginally and that is the point.
  - **P4b — extract the equipment-scoring cores** unlocked by P4a (equipment/scoring.py,
    tiers/equip_value.py; bridges to the EquipmentScoring/LoadoutProjection hand models).
  - **P4c — recipe_closure completeness invariant**: prove fuel = len(recipes)+1 suffices
    (every recursing frame marks a distinct key), upgrade the kernel-pinned completeness to a
    universal theorem, drop the pins.

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
- 2026-06-10: **P3a COMPLETE** (recipe family: recipe_closure + task_batch +
  task_reservation — the GameData-read Tier-4 trio). SRC HOIST
  (behavior-identical; all production callers untouched): each module split
  into PURE cores over plain data (recipes/drops Mappings + scalar state
  fields) + thin public wrappers reading the `crafting_recipes` /
  `resource_drops` accessors and forwarding. recipe_closure.py:
  `_closure_visited` (threaded visited-dict DFS), `_raw_units`,
  `_closure_demand` (per-path visited dicts) — all FUEL-BOUNDED with seed
  `len(recipes) + 1` (unreachable: every recursing frame marks a distinct
  recipe key; cyclic safety + fuel-0 base cases pinned by new unit tests) —
  plus `recipe_closure_pure`; visited sets are insertion-ordered
  `dict[str,int]` membership maps (assoc-list image). task_batch.py:
  `task_batch_size_pure` carries the WHOLE decision (gate + recipe traversal
  via cross-module calls into the recipe_closure cores + clamp).
  task_reservation.py: `task_reserved_demand_pure` / `consumes_reserved_pure`
  (presence read as `demand.get(r,0) != 0` — equal to the original `r in
  demand` on every core input since demands are built with multiplier ≥ 1,
  zero-qty edges skipped; the bridge carries the ≥1 invariant).
  EXTRACTOR (now v4, registry 9 modules): str literals (printable ASCII),
  registry-declared module-level int CONSTANTS (`BATCH_CAP`,
  `_MIN_FREE_SLOTS` → Lean defs), 3-arg `min`/`max` (Int, nested two-arg),
  `return {}` for dict returns, Pattern F `if X is None: <always-exits>`,
  tuple-target FIRST-MATCH loops (`for k, v in d.items(): ... return e`),
  and CROSS-MODULE calls: registry `imports` resolve against
  earlier-registered modules, emitted fully qualified
  (`Extracted.RecipeClosure._raw_units`) with matching
  `import Formal.Extracted.<Core>` header lines; fueled callees bridged by
  `Int.toNat` as before. Documented caveat: first extracted `//` — Lean
  `Int.fdiv` is total (divisor 0 → 0) where Python raises; divisors stay ≥ 1
  by construction. All 6 prior modules regenerate byte-identically.
  BRIDGES (Extracted/Bridges3.lean — new file, same `Extracted.Bridges`
  namespace; no sorry/admit/new axioms; core-only): encoding = injective
  `f : Nat → String` (injectivity needed: dict lookups are KEYED by codes,
  unlike combat_picker's payload-only codes), recipes as entry lists
  (`encRecipes`/`rOf`).
  - `task_batch_bridge` FULL: extracted = hand `batchSize` at the Python gate
    `eTaskGate` and the extracted plumbing terms `eMats`/`eHeld`;
    `task_batch_ge_one_extracted` transfers the floor-at-1 theorem.
  - `closure_demand_bridge` FULL (the workhorse): extracted threaded dict
    (replace-or-append `_dictSet`, fall-through max-record if) corresponds
    to hand `closureDemand` (prepend-record) via `DemRel` (pointwise lookups
    + two-way key sets), ∀ fuel/root/mult ≥ 1/graph/states — fuel induction
    outside, child-list induction inside (the hand `foldl_children_mono`
    pattern), with hand-side `DPos` (≥1) invariant lemmas.
    `reserved_demand_bridge` + `consumes_reserved_bridge` (bank some/none)
    give the API equalities; `task_reservation_done_inert_extracted`
    transfers contract (1); the 2026-06-09 helmet/bar/ore production trace is
    kernel-pinned on the extracted defs (deferred / surplus / done).
  - `raw_units_bridge` FULL: extracted `_raw_units` = `Int.ofNat ∘
    rawUnitsAux` ∀ fuel/graph/visited (foldl ↔ map-sum lemma).
  - recipe_closure is HONESTLY PARTIAL: `closure_visited_sound` +
    `recipe_closure_pure_sound` prove UNIVERSAL soundness against the
    least-fixpoint spec (`Reachable` / `isCraftable` / `isNeeded` — never
    over-collects); the COMPLETENESS direction (threaded-DFS analogue of the
    hand `satN` completeness) needs a formalized never-exhausts-fuel
    invariant — deferred; kernel-pinned on the registered mutation graphs
    (diamond 31, cycle 6, chain) extracted-vs-literal AND hand-vs-literal
    (`closure_pin_*`), and covered by the 240-case differential oracle.
  MUTATE.PY re-anchored (3+3+3, verified to match source exactly once +
  parse): task_batch clamp anchors unchanged, remaining-line retargeted into
  the pure core; task_reservation anchors retargeted (surplus `<=` via
  dict.get; remaining-scaling on `_closure_demand` call; task_type gate).
  HONEST FINDING: the closure DFS's own visited guard became
  OUTPUT-EQUIVALENT under the fuel bound (per-path fuel means every original
  call-tree path still runs unchanged; dropping the guard only re-explores)
  — a genuinely equivalent mutant — so the cyclic-safety-guard mutation now
  targets `_raw_units`, where revisit → 1 is value-bearing (manually
  verified killed: pinned cyclic case yields 12 ≠ 6).
  DIFF TESTS: task_batch suite de-monkeypatched (real one-recipe world
  realizes any (mats, held): T←M×mats, R drops M — the no-mock rule);
  recipe_closure fake replaced with a real GameData carrying the catalog.
  Wired: Formal.lean imports (3 extracted modules + Bridges3), Manifest
  #check block (22 entries), Audit #print axioms (22), check_extraction.sh
  covers modules 7-9 automatically. Gates green: lake build + oracle,
  no-sorry, axiom gate, extraction `--check` ×9, proof-concept index, orphan
  modules (139), manifest, recipe_closure + task_batch + task_reservation +
  items_task_run diff suites, full pytest 3096/100%, mypy strict (src +
  extractor), ruff. P3 remainder: inventory_caps (Tier 4) and the Tier-3
  float→Fraction cores (cycles_for_progress_core, scalar_core).
- 2026-06-10: **P3b COMPLETE** (inventory_caps — Tier 4: the per-item
  useful-quantity cap, the dominance gate and the LIVE space-driven
  overstock core). SRC HOIST (behavior-identical on every deterministic
  input; all production callers untouched — discard_overstock/guards use
  the preserved wrappers): `overstock_excess` was ALREADY pure and is
  extracted verbatim; `useful_quantity_cap[_excl_equipped]_pure` carry the
  whole cap decision over plain data (recipe_max + batch/safety scalars,
  task_type/task_code/total/progress with None→"" at the wrapper, the
  `crafting_recipes` mapping, action_cap from the config dict, and the
  is_equippable/is_dominated/hp_restore verdicts the `_cap_from_state`
  shell evaluates with the original lazy gating); `_task_chain_demand_pure`
  is the FUEL-BOUNDED recipe-chain demand (seed `len(recipes)+1`,
  unreachable — distinct key marked per recursing frame; per-path visited
  membership dicts, the P3a `_closure_demand` idiom; sum-generator →
  fold accumulator); `_is_dominated_pure` is the hand model's `Peer` fold
  over (fits, higher, covers, owned) verdict tuples. The unused
  `_task_chain_demand` wrapper became dead code and was removed.
  FLOAT BOUNDARY (P3c note): `_equip_value` stays float-typed and OUTSIDE
  the core — the wrapper evaluates the strictly-higher criterion into a
  Bool (exactly the hand `Peer.strictlyHigher` encoding); a float→Fraction
  refactor of `_equip_value` (and tiers/equip_value it mirrors) remains
  for P3c. fits/covers criteria also stay wrapper-side (per-peer GameData
  stats reads — data plumbing, not decision logic; the hand model has
  always taken them as Bools).
  HONEST FINDING (ordering divergence, P2c-class, resolved in the only
  deterministic direction): the original `_is_equippable_dominated`
  early-returned on a prefix sum while iterating an unordered SET — for
  negative owned counts (unreachable: counts are inventory+bank+equipped
  sums ≥ 0) the answer was ORDER-DEPENDENT, and the hand `isDominatedBy`
  has always been the order-independent total-sum threshold. Python's
  divergent-domain behavior was nondeterministic, so the hand model could
  not be aligned TO it (no deterministic spec exists); the core computes
  the total-sum threshold (equal to the prefix early-return on every
  deterministic input), making `dominated_bridge` UNIVERSAL with NO
  non-negativity hypothesis. At `slot_count ≤ 0` (excluded by the
  wrapper's `if not slots` guard) both sides agree (`true`).
  EXTRACTOR (now v5, registry 10 modules): n-ary `min`/`max` (right-nested
  two-arg, generalizing the 3-arg branch — 3-arg emission byte-identical),
  and parameter DEFAULTS restricted to int literals / registered int
  constants, IGNORED in emission (default application happens at Python
  call sites outside the extraction boundary; extracted call sites must
  pass full arity — `overstock_excess`'s watermark defaults). All 9 prior
  modules regenerate byte-identically.
  BRIDGES (Extracted/Bridges4.lean — new file, same `Extracted.Bridges`
  namespace; no sorry/admit/new axioms; core-only): NO Nat→String encoding
  needed (both hand models are component-parametric over Int).
  - `overstock_excess_bridge` FULL: extracted = `Formal.InventoryProfile.
    overstockExcess` ∀ inputs (the `repeat' split` + simp_all + omega
    cascade); transfers `overstock_profile_protection_extracted` (held ≤
    target ⇒ never shed) and `overstock_below_watermark_extracted` (free
    slots ⇒ no overstock) to the LIVE core.
  - `dominated_bridge` FULL: extracted fold = hand `isDominatedBy` over
    `encPeer`, ∀ peers/slot_count (foldl-shift + per-step `contribution`
    lemmas); `equip_cap_from_peers_extracted` composes the verdict into
    `equipCapFromPeers`. The caps diff test now runs the REAL
    `_is_dominated_pure` instead of its former inline Python mirror.
  - `cap_excl_bridge`/`cap_bridge` FULL at the extracted plumbing term
    `eTaskCap` (P3a `eMats`/`eHeld` style): extracted cap cores = hand
    `capExclWith`/`capWith` with components `equipCapValue`/
    `consumableCapValue`/`eTaskCap` (the 5-way max nests identically);
    transfers `cap_equipped_ge_one_extracted` and
    `cap_safety_floor_extracted`.
  - `_task_chain_demand_pure` is extracted-only (the hand `capExclWith`
    takes `taskRemaining` as an INPUT — the chain computation never had a
    hand model): universal lemmas `chain_demand_fuel_zero` /
    `chain_demand_target_self` / `chain_demand_visited_blocked` +
    kernel pins `chain_pin_cycle` (self-referential recipe → 0) and
    `chain_pin_ash` (the 2026-06-05 ash_plank→ash_wood 1:1 trace → 10);
    covered by the 300-case differential oracle.
  MUTATE.PY re-anchored (3 inventory_caps + 5 inventory_profile anchors
  verified to match source exactly once + parse): the equipped-floor
  mutation retargeted into `useful_quantity_cap_pure` (`return max(1,
  base)` → `return base`, same semantic intent, killed by
  test_equipped_floor_binds_against_lean); safety-clamp and overstock-+1
  anchors unchanged (the clamp line moved into the core verbatim);
  all 5 overstock_excess anchors untouched (function extracted verbatim).
  DIFF TESTS: caps suite de-monkeypatched (real GameData: one-recipe world
  `END ← demand × code` realizes any max_recipe_demand; real ItemStats
  catalog — the no-mock rule), dominance suite runs the real core.
  New unit tests pin the fuel-0 base, the visited cycle guard, the
  target-hit short-circuit, the excl-equipped wrapper and the dominance
  threshold boundary.
  Wired: Formal.lean imports (Extracted.InventoryCaps + Bridges4),
  Manifest #check block (14 entries), Audit #print axioms (14),
  check_extraction.sh covers the 10th module automatically. Gates green:
  lake build + oracle, no-sorry, axiom gate, extraction `--check` ×10,
  inventory_caps + inventory_profile + inventory_chain_safe diff suites,
  full pytest 100%, mypy strict (src + extractor), ruff. P3 remainder:
  the Tier-3 float→Fraction cores (cycles_for_progress_core, scalar_core)
  and the P3c `_equip_value` float boundary noted above.
- 2026-06-10: **P3c COMPLETE** (the Tier-3 float cores: cycles_for_progress
  + scalar_yield, refactored to EXACT `Fraction` arithmetic, extracted and
  bridged — P3 closed).
  SRC REFACTORS (verified vs the old implementations over 20k randomized
  streams incl. mixed-None; all production callers untouched):
  cycles_for_progress_core.py: the decision arithmetic lives in
  `cycles_for_progress_exact` (Fraction|None) — the two interval scans are
  single-accumulator folds over per-cycle steps `_strict_step` (threads the
  `(intervals, last_progress_at, prev_progress)` tuple; `prev` ALWAYS
  overwritten, so a None reading resets the detector) and `_satisfy_step`;
  `statistics.median` replaced by `_median_exact` (explicit sorted-list
  median; even count = exact `Fraction(a+b, 2)`). The public
  `cycles_for_progress_pure` keeps `float|None` by converting ONCE at the
  boundary: odd-count medians are ints (exact in float « 2^53; the wrapper
  now returns the numerically-equal float where statistics.median returned
  int); even-count `float(Fraction(a+b,2))` is bit-identical to the former
  `(a+b)/2` float division (both round-to-nearest of the same rational);
  `warmup<=0`+empty now raises IndexError where StatisticsError raised
  (unreachable: the only caller passes WARMUP_MIN_SAMPLES=10).
  scalar_core.py: `scalar_yield_exact` is the Fraction-only core (membership
  weight-selection inlined into the fold; `Fraction(level+1)` lift); the
  public `scalar_yield_pure` keeps the float API by lifting EVERY input
  exactly (`Fraction(float)` is the exact binary expansion — 0.2 stays the
  precise double it always was), running the exact core and rounding ONCE —
  results can differ from the old per-op float arithmetic in last ULPs
  (checked: no test pins shifted; all pins are integer-exact or toleranced).
  `coins_spent_from_delta` was already in-subset and extracted verbatim.
  _EQUIP_VALUE DECISION (the P3b note): `inventory_caps._equip_value` →
  `int` (every summand is an int; the strictly-higher dominance criterion is
  now EXACT integer arithmetic; verdicts identical — float(int) compared
  ints all along). It stays wrapper-side data plumbing (per-peer GameData
  stats reads; the hand model takes the verdict Bools). NOT cascaded:
  `tiers/equip_value.equip_value` and the equipment-scoring system stay
  float — a full Fraction migration would touch tiers/objective.py
  (tier ranking tuples), tiers/strategy.py (gain = max(0.0, ev - current)),
  tiers/prerequisite_graph.py, goals/progression.py,
  goals/upgrade_selection.py (`value: float`) and every marginal/ranking
  consumer downstream — deferred, scoped honestly here.
  MODEL-FIDELITY FINDING (P2c-class, fixed): the hand `strictIntervalsAux`
  KEPT `prevProgress` through a `none` task_progress row; Python overwrites
  `prev_progress` every iteration (None RESETS the detector). Genuinely
  divergent on mixed None/int streams (chronological `0, none, 5, 7`:
  Python no strict interval; old model `[1]`) — masked because the diff
  generator only built all-None or all-int progress streams (the P2c
  tree-only-domain gap class). Python is the spec: hand model aligned
  (`| _, none => aux none ..`), `strictIntervals_pos` re-proved, reset
  witness kernel-pinned, generator now MIXES None gaps, diff suite pins the
  reset (`test_none_reading_resets_strict_detector`).
  EXTRACTOR (now v6, registry 12 modules): `sorted` on list[int] → emitted
  `_sortInt` insertion sort (int-multiset sorting is order-independent =
  Timsort-value-equal); list[int] subscript → emitted total `_nthInt`
  (out-of-range 0, negative clamps — Python raises/wraps; in-range by
  construction); non-empty list literals incl. starred segments
  (`[*xs, v]` → `xs ++ [v]`); `+` list concatenation → `++`;
  `list(reversed(xs))` → `List.reverse`; `Fraction(a)`/`Fraction(a, b)` →
  `mkRat a 1`/`mkRat a b` (CAVEAT: `mkRat a 0 = 0` where Python raises —
  literal non-zero denominators only); Rat `*` and `/` (CAVEAT: Rat
  division total, `x/0 = 0` — divisors non-zero by construction,
  gold_per_xp=100); `x in xs` (str/int over list/frozenset image) →
  `List.contains` (membership is order-independent — setlike safe);
  AnnAssign tuple literals coerced componentwise (`([], None, None)`).
  All 11 prior modules byte-identical (InventoryCaps.lean: sha header only,
  from the `_equip_value` source edit — emitted body byte-identical).
  BRIDGES (Extracted/Bridges5.lean — new file, same `Extracted.Bridges`
  namespace; no sorry/admit/new axioms; core-only). FLOAT BOUNDARY
  DOCUMENTED THERE: every proof is on the exact Rat cores; the wrappers'
  single `float()` conversion is the new trusted seam OUTSIDE the proofs,
  SAMPLED by the diff suites (wrapper == float(exact) asserted on every
  generated input; the exact cores vs the Lean oracle compared with NO
  tolerance — the old `limit_denominator` bridge is gone).
  - `cycles_for_progress_bridge` FULL: extracted = hand
    `cyclesForProgressPure` ∀ streams (encCycleRow embedding) and ∀ Nat
    warm-ups; built from universal component bridges `cycles_sort_bridge`
    (emitted sort = `insSortInt`), `cycles_nth_bridge`,
    `cycles_median_bridge` (∀ lists, empty included — both sides 0),
    `cycles_strict_fold_bridge` (true ONLY with the None-reset fix) +
    `cycles_satisfy_fold_bridge` (snoc/cons via append assoc) +
    `revList_eq_reverse`. Transfers: `cycles_median_concat_extracted`
    (THE verdict-(b) dual-signal contract) and
    `cycles_warmup_blocks_extracted`.
  - `scalar_yield_bridge` FULL: extracted = hand `scalarYield` ∀ rational
    inputs, over the `encSkillTerm` membership/weight embedding, level cast
    to Rat (`mkRat (level+1) 1 = ↑level + 1`), hand `goldUnit` at
    `1/gold_per_xp` (`Rat.div_def`). Transfers gold monotonicity
    (`scalar_yield_mono_gold_extracted`). `coins_spent_bridge` is `rfl`;
    inversion transferred.
  MUTATE.PY re-anchored (5 scalar + 3 cycles, verified to match source
  exactly once + parse): weight-swap retargeted into the inlined fold
  selection; float-seed retargeted to `Fraction(0)` → `0.0` (kills the
  exact-Fraction identity); satisfy-gate flip retargeted to the
  `cts is None` early return (None rows now TypeError on `<= 0`);
  strict off-by-one retargeted to the inverted early return
  (`tp <= prev` → `tp < prev`, same semantic mutant); gold/coin/coins_spent
  anchors unchanged (lines moved into the exact core verbatim).
  DIFF TESTS: both suites now drive the EXACT cores against the oracle
  (Fraction == num/den, zero tolerance) + sample the float seam; cycles
  generator upgraded to mixed-None progress streams; new reset-semantics
  pin. New unit tests (tests/test_ai/test_cycles_for_progress_core.py) pin
  every branch deterministically (odd/even median, reset, dual signal,
  non-positive satisfy, warm-up, float boundary).
  Wired: Formal.lean imports (Extracted.{CyclesForProgress,ScalarCore} +
  Bridges5), Manifest #check block (12 entries), Audit #print axioms (12),
  check_extraction.sh covers modules 11-12 automatically. Gates green:
  lake build + oracle, no-sorry, axiom gate, extraction `--check` ×12,
  orphan modules (144), proof-concept index, cycles_for_progress +
  scalarizer + inventory_caps + inventory_profile + inventory_chain_safe
  diff suites, full pytest 3113/100%, mypy strict (src + extractor), ruff.
  P3 CLOSED. Remaining standing item: the StepDispatch.lean min_gathers
  consume-semantics alignment flagged in P2c.
- 2026-06-10: **P3d COMPLETE** (min_gathers consume-semantics alignment +
  extraction — P3 fully closed incl. min_gathers; no standing items remain).
  DIVERGENCE CONFIRMED (the P2c pattern, exactly as flagged): the hand
  `Formal.StepDispatch.minGathers` credited a CONSTANT `owned` function per
  node while `min_gathers.py` threads and CONSUMES a copy — equal on TREE
  recipes (the old generator's `claimed`-set domain), genuinely divergent on
  DAGs. Witnesses: shared-raw `{root:{a,b}, a:{m:1}, b:{m:1}}, owned {m:1}` —
  Python 1 vs hand 0; diamond at per-unit 2 — Python 2 vs hand 0.
  SRC REFACTOR (behavior-identical — verified old == new over 20k randomized
  DAG trials; all production callers untouched): `_min_gathers` now threads an
  explicit `(total, owned)` state tuple and a fuel that `min_gathers` seeds
  with `len(recipes) + 1` (unreachable on acyclic recipes — every recursing
  frame expands a distinct craftable along its path; a cyclic recipe now
  terminates with the node's quantity accounted as raw — conservatively LARGE,
  the unreachability gate stays sound — instead of RecursionError, pinned by a
  new unit test). The fuel-0 base mirrors the old hand model's
  account-the-need-as-raw choice.
  HAND MODEL (StepDispatch.lean, rewritten in place on the shared extracted
  encoding — `Formal.ShoppingList.Dict/Recipes/getD/setD`, String items, Int
  quantities, fuel-structural recursion; the stale tree-only-scope comment
  corrected). THEOREM LEDGER (nothing became false; every obligation re-proved
  under consume semantics):
  - re-proved (same names, consume signatures): `minGathers_raw` (raw node =
    the per-node `Formal.ShoppingList.deficit`), `minGathers_raw_unowned`
    (flat `qty`), `gatherTarget_step_only_when_root_over_budget`,
    `gatherTarget_root_when_feasible`, `gatherTarget_step_not_harder_than_root`
    (now with the explicit production-invariant hypotheses `0 ≤ held`,
    `0 ≤ stepQty` the Nat encoding used to carry implicitly). `gatherTarget`
    drops the fuel parameter — like the Python, the cost is the SEEDED
    `minGathersCount` (new def mirroring the public `min_gathers`).
    New `minGathers_succ` zeta-expansion equation (proof plumbing).
  - dropped defs: `Recipe` (Nat-fn encoding), `gdeficit`, `sumGathers` (the
    unfaithful constant-credit mutual — superseded, not falsified; no
    downstream citations remained).
  - new DAG witnesses kernel-pinned: shared-ore (2 not 0) + diamond (2 not 0).
  EXTRACTION (registry 13 modules): `MinGathers.lean` generated from
  `min_gathers.py` (`_min_gathers`, `min_gathers`) — pure, no GameData reads,
  no extractor extensions needed (the shopping_list state-threading idiom).
  All 12 prior modules regenerate byte-identically.
  FULL BRIDGE (Extracted/Bridges6.lean — new file, same `Extracted.Bridges`
  namespace; no sorry/admit/new axioms; core-only): `min_gathers_node_bridge`
  (extracted `_min_gathers` = hand `minGathers` ∀ fuel/item/qty/recipes/state
  — fuel induction, the P2c `shopping_expand_bridge` technique),
  `min_gathers_bridge` (API = `minGathersCount`),
  `min_gathers_raw_unowned_extracted` (flat-gather contract transferred), DAG
  double-credit witness pinned on the extracted def.
  ORACLE: `runGatherStepTarget` rebuilt on the String/assoc-list encoding;
  the `fuel` wire arg DROPPED (the model seeds it internally, like Python).
  DIFFERENTIAL: generator upgraded trees → DAGs (the `claimed` single-parent
  set removed — tree-only generation is what masked the divergence); pinned:
  `test_dag_double_credit_witness_routes_to_step` (cost 1 consume vs 0
  constant-credit flips the routing at budget 0),
  `test_dag_diamond_one_path_covered` (2 vs 0 at budget 1),
  `test_partial_credit_keeps_root` (50 vs 80 at budget 60 — kills the
  uncredited-recursion mutant); stale tree-only docstring corrected.
  MUTATE.PY: 4 new MIN_GATHERS_MUTATIONS (never-credit, never-consume — the
  constant-credit regression, DAG-killed —, uncredited recursion, raw-leaf-
  free), each verified to match source exactly once + parse + be KILLED by a
  named deterministic pin (in-memory check; mutate.py not run); the 3
  gather_step_target anchors unchanged and re-verified.
  Wired: Formal.lean imports (Extracted.MinGathers + Bridges6), Manifest
  #check block (3 entries), Audit #print axioms (3), StepDispatch imports
  Formal.ShoppingList (core-only, shared encoding); check_extraction.sh
  covers the 13th module automatically. New unit tests: DAG consume witness,
  cyclic-recipe termination. Gates green: lake build + oracle, no-sorry,
  axiom gate, extraction `--check` ×13, gather_step_target diff suite (DAG
  domain), full pytest 100%, mypy strict (src + extractor), ruff.
- 2026-06-11: **P4c COMPLETE** (recipe_closure completeness: kernel pins →
  universal theorem; Lean-only, zero Python changes). The never-exhausts-fuel
  invariant is formalized in Extracted/Bridges3.lean over the extracted defs:
  `unmarkedKeys recipes v` (recipe entries whose key is unmarked in the
  threaded visited dict) is THE fuel measure — every recursing frame of
  `_closure_visited` first marks a previously-unmarked recipe key
  (`unmarkedKeys_strict`), marks only grow (`closure_visited_msub` /
  `MSub`), so the measure strictly decreases down every recursion path and
  the wrapper seed `len(recipes)+1` strictly dominates it at every state
  (`eFuel_sufficient`) — the fuel-0 arm is unreachable on frames with work
  pending. `closure_visited_complete` (fuel induction outside, child-list
  fold induction inside, the P3a bridge idiom): with fuel above the measure
  the DFS marks its root AND leaves every newly marked key children-closed;
  the roots fold (`roots_fold_complete`) yields a `MarkedClosed` dict
  containing every root, and `Reachable` induction transfers EVERY
  spec-reachable item into the marked set
  (`closure_visited_marks_reachable`). Output completeness
  `recipe_closure_pure_complete` (isCraftable ⇒ in craftables, isNeeded ⇒ in
  needed) and the combined iff `recipe_closure_pure_spec` (output membership
  ⟺ isCraftable / isNeeded, ∀ graph/drops/roots, same injective-embedding
  framing as the soundness theorems). PINS: the six `closure_pin_*`
  completeness pins (diamond/cycle/chain + matches_hand, plus their `pinF` /
  chain fixtures) are SUPERSEDED and dropped; `raw_units_pin_diamond` /
  `raw_units_pin_cycle` KEPT — they pin exact numeric quantity outputs
  (31; 6 vs the mutant's 12) that the universal set-membership statement
  does not, and the mutation suite cites them. mutate.py recipe_closure
  anchors and the diff test are UNCHANGED (mutants killed by the Python
  diff suite, which still passes). Wired: Manifest #check (+5 new, −6 pins),
  Audit #print axioms (same), Bridges3 module docstring updated. Gates
  green: lake build + oracle, no-sorry, axiom gate (safety ⊆ kernel three),
  extraction `--check` ×13, recipe_closure diff suite 3/3. P4 remainder:
  P4a/P4b (equipment scoring, concurrent separate task).
- 2026-06-11: **P4a COMPLETE** (equipment scoring float → EXACT arithmetic;
  the P3c deferred cascade). TYPE DECISIONS (int where all summands int,
  Fraction where division/blending appears):
  - `tiers/equip_value.py`: `equip_value`/`tool_value` → **int** (every
    summand is an int ItemStats field; the `float()` wrappers added
    nothing; the Lean `EquipValueAugmented.equipValue : Int` hand model now
    matches the Python type, not just its values). `equipment/scoring.py`
    was ALREADY exact int (prior phase) — untouched.
  - `tiers/prerequisite_graph.py`: best-weapon tuple → `tuple[int, str]`.
  - `goals/upgrade_selection.py`: `UpgradeCandidate.value` → **int**; key
    tuples all-int. Hand model `UpgradeSelection.lean` was already Int.
  - `goals/progression.py`: `_upgrade_value` → int. The float `-inf`
    missing-stats sentinel (`_value_of`) RETIRED: `_value_candidate` yields
    NO candidate when stats are missing (`best_by_value` already treats
    None as always-loses). Verdict parity everywhere except the
    production-unreachable both-sides-missing corner (was the inv pick,
    now None) — pinned by updated coverage tests citing P4a. Goal.value()
    bands (35/51) stay float — goal-priority API, not equipment scoring.
  - `tiers/objective.py`: gear_gaps → `dict[str, int]`; ObjectiveGap
    fractions → **Fraction** (integer gap / integer denominator, exact).
  - `tiers/objective_completion.py` + `tiers/personality.py`: pure-core
    annotations + `category_weight` → Fraction (BalancedPersonality →
    Fraction(1)); bodies unchanged (mutation anchors preserved).
  - `tiers/strategy.py`: the WHOLE ranking pipeline → **Fraction** (priors
    2/5, 3/5, 3/10; CHAR_GAP_PER_LEVEL 3/50 — 0.06 was never a real
    double; GEAR_EQUIP_SCALE 20; STICKY 3/2; urgency 2; XP_RATE_REFERENCE
    10); gear gain `max(0, equip_value − current)` exact int before the
    Fraction normalisation; the learned float yield lifted ONCE via
    `Fraction(y.char_xp)` (P3c boundary idiom). RootScore score fields →
    Fraction with a `to_dict` float conversion (trace-only JSON seam,
    never read back). CRITICAL_HP_FRACTION stays float (hp guard, out of
    scope).
  - `tiers/strategy_blend.py`: balancing/blend_weight/learned_blend →
    Fraction (BALANCE_K = 1/4 etc.); `blend_weight`'s `n / 20` float
    rounding GONE (20 not a power of two — the one genuinely inexact op).
  - `tiers/decide_key.py`: `neg_final` → Fraction (exact lex sort).
  HONESTY (the plan's note, measured): 200k-pair randomized old-vs-new
  sweep: **0 strict order inversions**; 92 float-STRICT pairs are now
  EXACT TIES (witness: gather 2/5·1/5·3/2 vs consumable 3/10·1/5·2 — both
  3/25; float said 0.12000000000000002 > 0.12 by rounding noise; exact
  ties fall to the documented effort/repr tiebreaks); 38 sticky-gate
  boundary comparisons shift. NO pinned diff-oracle decision flipped (all
  suites green with their verdict assertions unmodified).
  DIFF ORACLES re-pinned exact: strategy_blend now compares the PRODUCTION
  `balancing` Fraction to the Lean Rat oracle directly (the
  `_balancing_fraction` local mirror deleted; float-exactness caveats
  gone; constants pin sharpened to Fraction); objective diff drops the
  `int(equip_value(...))` / `int(sum(gear_gaps))` boundary casts and adds
  exact `Fraction(num, den)` pins for all three gap fractions;
  upgrade_selection diff drops the `float(value)` / `int(c.value)` lifts;
  weighted_remaining diff's `type: ignore[arg-type]`s removed (annotations
  now match the exact domain). equipment_scoring + loadout_projection
  diffs were already bit-exact int — untouched. NO Lean changes needed:
  every hand model (EquipValueAugmented, UpgradeSelection, Objective,
  StrategyBlend, WeightedRemaining, DecideKey, RankingComposition) was
  already Int/Rat.
  MUTATE.PY: 2 strategy_blend anchors re-anchored (slope flip on the new
  `raw = 1 + ...` text; `BALANCE_K = Fraction(1, 4)` → `Fraction(1)`, same
  0.25→1.0 intent) + 1 NEW byte-equivalence mutant (float-seed balancing
  `1 → 1.0`, the scalar_core idiom) with a deterministic isinstance kill
  added to the threshold-identity diff test; all three verified killed
  in-memory (mutate.py NOT run). All 267 anchors across 89 groups verified
  to match source exactly once + parse. Every other group (objective,
  strategy traversal, upgrade_selection, weighted_remaining, scoring,
  progression, decide_key) anchors on unchanged lines.
  Gates green: full pytest 3116/100%, mypy strict (201 files), ruff
  src+tests (formal/diff at its pre-existing 100-error unlinted baseline),
  lake build + oracle, no-sorry, axiom gate, extraction `--check` ×13
  byte-identical (none of the touched files are extracted modules — that
  is P4b). Scoped diff suites green: equipment_scoring, loadout_projection,
  upgrade_selection, objective, strategy_blend, arbiter_select,
  weighted_remaining, decide_key, prerequisite_graph, strategy_traversal,
  goal_system_value, goal_value_band_safety, realizable_loadout.
  P4b (extract the now-exact equip cores) unlocked.
- 2026-06-11: **P4b COMPLETE — P4 FULLY CLOSED** (extract the exact
  equipment-scoring cores; registry 13 → 15 modules, two files: scoring.py
  and equip_value.py each get their own generated module).
  ENCODING DECISIONS (hoist-to-plain-params, the P3a wrapper pattern; the
  hand models' input shapes drove every choice):
  - `equipment/scoring.py`: new pure cores `weapon_score_raw_pure` /
    `weapon_score_pure` / `gather_score_pure` / `armor_score_pure`; the
    public functions became thin wrappers (signatures unchanged). The
    ItemStats reads (`weapon.attack`, `.subtype`, `.skill_effects`,
    `armor.resistance`) hoist to plain dict/str params; the module-level
    `ELEMENTS` tuple hoists to a `list[str]` parameter (wrapper passes
    `list(ELEMENTS)`) — the hand `WScore`/`AScore` fix `elements` as a
    concrete list, so the bridge instantiates the parametric extracted def
    at the encoded element list. Loop bodies rewritten single-accumulator
    (`score = score + ...`) to fit the v6 subset.
  - `tiers/equip_value.py`: new pure cores `equip_value_pure` (seven plain
    params: six summed ints + subtype — EXACTLY the hand RawStats + isTool
    shape, the wrapper hoists the dict-value sums) and `tool_value_pure`
    (the wrapper keeps the redundant empty-dict fast path).
  EXTRACTOR: registry-only extension (+2 ModuleSpecs appended; ZERO new
  constructs — the v6 subset already covered every shape); prior 13 modules
  regenerate byte-identically (`--check` ×15 OK).
  BRIDGES (Formal/Extracted/Bridges7.lean, all FULL universal, no sorry,
  axioms ⊆ kernel three): element-keyed score bridges are universal over an
  arbitrary INJECTIVE `Int→String` element embedding (the CombatPicker
  precedent): `weapon_score_raw_bridge` (= hand WScore), `armor_score_bridge`
  (= AScore), `weapon_score_bridge` (= PurposeRouting.combatScore with
  isTool = `subtype == "tool"`), `equip_value_bridge` (= EquipValueAugmented
  .equipValue, pointwise over ALL stats — the wrapper's already-summed
  encoding matches the hand RawStats directly). `tool_value_pure` has no
  standalone hand model (disclosed): its bridge is the CROSS-CORE duality
  `tool_value_abs_gather` (= |gather_score_pure|, definitional) +
  `tool_value_neg_gather_on_tools` (tool domain: max tool_value ≡ min
  gather_score — the upgrade ranking and the gather picker agree).
  TRANSFERRED hand theorems onto the extracted defs:
  `weapon_score_raw_nonneg_extracted` (THE clamp theorem),
  `weapon_score_strict_extracted` + `weapon_score_tiebreak_extracted`
  (strict-order protection + the fishing_net invariant),
  `pickslot_no_downgrade_extracted` (pickSlot instantiated at the extracted
  score), `gather_pick_optimal_extracted` (pickGatherSlot_score_optimal at
  the extracted gather score), `gather_score_absent_zero`,
  `equip_value_strict_extracted` + `equip_value_tiebreak_extracted`.
  MUTATE.PY: 2 equipment_scoring anchors re-anchored onto the pure-core
  lines (clamp drop; armor float-rescale — same intents; the wrappers
  delegate so mutants still flow into the diff oracle); both verified
  killed in-memory (clamp: 0 vs -100 at res=120; rescale: 21 vs 0.21);
  all 267 anchors across 89 (src, group) pairs verified to match exactly
  once + parse (mutate.py NOT run). Coverage: one new unit test pins the
  `weapon_score_raw` wrapper + the composite `2*raw + bonus` identity.
  Wired: Formal.lean (+3 imports), Manifest #check (+15), Audit #print
  axioms (+15). Gates green: lake build + oracle, no-sorry, safety +
  liveness axiom gates, no-orphan (149 modules), extraction `--check` ×15
  byte-identical, full pytest 3117/100%, mypy strict (202 files), ruff,
  scoped diff suites (equipment_scoring, loadout_projection, objective,
  upgrade_selection, realizable_loadout). With P4a + P4c already closed,
  the P4 deferred ledger is EMPTY — every pure decision core registered to
  date ships with an extracted, bridge-proved Lean model.
