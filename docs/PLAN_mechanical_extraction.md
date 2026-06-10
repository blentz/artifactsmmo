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
