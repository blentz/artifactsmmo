# Development

Python 3.13, managed with [`uv`](https://docs.astral.sh/uv/). Prefix every
command with `uv run` so the virtualenv is active.

```sh
uv sync                 # install deps (lockfile committed)
uv run pytest           # test suite
uv run mypy src         # type check
```

Testing bar: 0 errors, 0 warnings, 0 skipped, 100% coverage. Tests live in
`tests/`. One behavioral class per file.

## Formal verification

The decision core is proven in **Lean 4** over all inputs, and the running
Python is held to the proofs by a differential + mutation gate: the same
inputs are run through both the Lean model and the Python implementation and
must agree, and mutating the implementation (or weakening a theorem) must
fail the build. Proofs and the gate live under `formal/`.

## Design docs

Architecture, design rationale, and implementation plans live under
`docs/superpowers/`:

- `specs/2026-05-12-goap-ai-player-design.md` — initial GOAP design
- `specs/2026-05-15-goap-robustness-layer-design.md` — survival layer
- `specs/2026-05-17-autoregressive-planning-design.md` — learning store
- `specs/2026-05-18-strategic-reasoning-design.md` — per-cycle scoring
- `specs/2026-05-18-max-level-objective-design.md` — root objective
- `specs/2026-06-13-tui-map-sprites-design.md` — half-block sprite map + 3×3 layout
- `specs/2026-06-13-improved-sprites-design.md` — outline-only sprite tileset
- `specs/...` — one spec per feature; `plans/...` — task-by-task implementation plans

Per-feature notes and postmortems live alongside in `docs/` (`PLAN_*.md`,
`IMPLEMENTATION_SUMMARY_*.md`, `docs/postmortems/`).
