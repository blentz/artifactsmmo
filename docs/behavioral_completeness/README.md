# Behavioral Completeness Program

This program asks a single question of the AI player: of everything the game's
API lets a character *do*, which behaviors does the bot actually exercise, and
which of those are backed by a kernel-checked proof? It pairs a **behavioral
completeness audit** (does a goal/means/guard handle each game concept at all?)
with a **proven core** (is the decision logic for that behavior verified in
Lean 4 over all inputs?). The audit is captured as a cited, lint-enforced
matrix; gaps are ranked by live-bottleneck leverage; and every proof is
cross-linked to the concepts it covers so coverage claims stay honest.

Read these together:

- [`MATRIX.md`](MATRIX.md) — 17 concept sections, 7 cited fields each: player→concept actions, concept→player grants, strategic use, opportunity cost × content tier, behavior coverage, proof coverage, and gap+policy.
- [`PROOF_CONCEPT_INDEX.md`](PROOF_CONCEPT_INDEX.md) — generated inverse of the matrix proof column: every Lean module → its `@concept` / `@property` tags. A concept with no module, or a module with no tag, is a traceability gap.
- [`BACKLOG.md`](BACKLOG.md) — gaps ranked by `journey_impact × live_bottleneck × stall_risk` (read from live traces); `IGNORE` gaps score 0.
- [`content_tiers.md`](content_tiers.md) — the generated journey axis (T1→T6) the opportunity-cost column cites.
- Spec: [`../superpowers/specs/2026-06-06-behavioral-completeness-design.md`](../superpowers/specs/2026-06-06-behavioral-completeness-design.md)
- Plan: [`../superpowers/plans/2026-06-06-behavioral-completeness-phase0-1.md`](../superpowers/plans/2026-06-06-behavioral-completeness-phase0-1.md)

## How to regenerate

- `uv run python scripts/gen_content_tiers.py` — regenerates `content_tiers.md` (the journey axis) from game data.
- `uv run python scripts/gen_proof_concept_index.py` — regenerates `PROOF_CONCEPT_INDEX.md` from the `@concept`/`@property` tags on `formal/Formal/*.lean`.
- `formal/gate/check_proof_concept_index.sh` keeps the committed index honest: it fails the build if a tag changes without the index being regenerated.
- The matrix itself is kept structurally honest by `artifactsmmo_cli.audit.matrix_lint.lint_matrix` (every section must carry all seven fields, each non-placeholder, with a citation on every strategy field).

## Status

**Phase 1 complete (audit done). Entering Phase 2 — gap closure.**

The top-3 BACKLOG items become the first Phase-2 specs:

1. **resources (THIN, score 27)** — prove gather-yield optimality; this is the live bottleneck (gather → craft → equip chain for current gear).
2. **crafting (UNPROVEN, score 27)** — prove the workshop-routing + craft-vs-buy decision.
3. **tasks (UNPROVEN, score 18)** — prove `PursueTask` reachability (an items-task run terminates).

## Proof property classes

Every new behavior Phase 2 lands must hold the relevant ones of these four
proven property classes (the `@property` tags in the index):

- **dominance / monotonicity** — the chosen action/loadout/target is at least as good as every alternative, and improving an input never worsens the decision.
- **totality / no-deadlock** — the decision is defined on every reachable state; some action is always selectable (no stuck state).
- **safety** — projection/apply never violates an invariant (no inventory overflow, no banking a needed input, no unwinnable engagement).
- **reachability** — the goal state is actually reachable through the exposed action set (the plan can flip the goal from false to true).
