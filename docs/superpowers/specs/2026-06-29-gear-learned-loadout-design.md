# Sub-project D — Learned Combat-Loadout Diagnostics — Design

**Status:** approved (brainstorm 2026-06-29) · **Epic:** Holistic Gear-Loadout
Architecture (`2026-06-28-gear-loadout-architecture-design.md`, on main).
**Branch:** `feat/gear-learned-loadout` (off main = sub-project C merged, tip `725b6836`).
**Build order:** sub-project 5 of 5 (A ✅ → ruler ✅ → B ✅ → C ✅ → **D**) — the final epic
sub-project.

## Why

The epic's D was "learned per-monster loadout: persist the loadout that actually won + its
predict_win verdict vs the real outcome; reuse the learned best; refine on loss." Given what's
already built — C records a per-task loadout on a win, the learned-loss veto (`is_winnable`)
already avoids losing *monsters*, and `predict_win` is the kernel-proven capability ceiling —
the **behavior-change** increment (prefer-learned-loadout + refine) is speculative and would
couple new logic into the proven combat path. **Approved scope: diagnostic-only.** D *captures
the ground-truth data* (what loadout actually fought, what predict_win said, what happened) and
exposes it in a read-only report, **changing no bot behavior**. This grounds any future
"prefer learned loadout" sub-project in real calibration data and surfaces where `predict_win`
mis-predicts — at near-zero risk.

## Scope (approved decisions)

- **Diagnostic-only — NO behavior change.** D does not alter which loadout the bot equips, nor
  `predict_win`/`is_winnable`. The proven combat path is untouched.
- **Surface = new table + accessor + a read-only CLI report** (mirroring the `macro-research`
  analyzer), so the data is viewable now, not just stockpiled.
- **No formal lockstep.** D drives no bot decision (pure recording + read-only aggregation), so
  there is no decision logic to mirror in Lean. Justified coverage-carve from the gate's
  differential/mutation (documented in `formal/README.md`); D adds no Lean and changes no proved
  core, so `formal/gate.sh` stays green untouched.

## Architecture

Four small units; the bot's combat path is untouched:
- **`CombatLoadoutOutcome` table** (`LearningStore`, `learning/models.py`): **append-per-fight**
  (calibration history, NOT last-write-wins). Columns: `id` (autoincrement PK), `character`,
  `task_key` (`combat:<monster>`), `loadout` (JSON of the worn equipment, slot→code),
  `predicted_win` (bool), `actual_win` (bool).
- **Recording hook** (`player.py`): a sibling to C's `_record_loadout_for_action`, fired for
  every `FightAction` resolution on **win OR loss** (NOT gated on `outcome=="ok"` — the existing
  C hook is). Best-effort (`record_*` swallows `SQLAlchemyError`).
- **Accessor** (`LearningStore.combat_loadout_outcomes() -> list[...]`): reads the rows
  (best-effort, `[]` on error) for the report + any future consumer.
- **Read-only CLI report** `artifactsmmo combat-loadout-report` (registered in `main.py` beside
  `macro-research`; `commands/combat_loadout_report.py` thin glue + a pure aggregator/formatter
  under `ai/macro/`), read-only over `learning.db`.

## Data model + recording

At each `FightAction` resolution the hook records, from `prev_state_for_learning` (the state
that fought):
- **`task_key`** = `combat:<monster_code>` (reuses C's `combat_key`).
- **`loadout`** = the **actually-worn** equipment (`prev_state.equipment`, non-`None` slots,
  JSON `sort_keys=True`) — ground truth "what fought," distinct from C's *computed-best*
  `pick_loadout`.
- **`predicted_win`** = `predict_win(prev_state, game_data, monster_code)` evaluated at fight
  time.
- **`actual_win`** = `outcome == "ok"` (a loss surfaces as `outcome == "error:fight_lost"`).

**Documented nuance:** `predict_win` internally models the *best on-hand* loadout (it calls
`pick_loadout`), whereas `loadout` is what was *actually* worn. So a row means "predict_win said
the best on-hand loadout could win; the bot fought wearing X; result was Y." That is exactly the
useful calibration signal (e.g. *predicted-winnable but lost wearing X*). D does NOT re-run
predict_win per-specific-loadout (predict_win takes no loadout arg; changing it would touch the
proven veto — out of scope).

## The read-only CLI report

`artifactsmmo combat-loadout-report` mirrors `macro-research`'s shape (typer `--db`/`--out`
options + a `_default_db_path()` to `~/.cache/artifactsmmo/learning.db`; load rows → aggregate
with a PURE function → `format_report`-style markdown → print or write). Per `task_key` it prints:
- **predict_win calibration**: predicted-win rate vs actual-win rate over recorded fights, and
  mis-prediction counts split into the two informative buckets — *predicted-winnable but lost*
  (over-estimate) and *predicted-unwinnable but won* (under-estimate).
- **per-loadout outcomes**: for each distinct worn `loadout`, its win/loss tally — which
  actually-worn loadouts win and which lose against that monster.
- a ranked summary (worst predict_win calibration first) to point a future behavior-change
  sub-project at the real gaps.

The aggregator is a pure `(rows) -> report-model` function (unit-tested in isolation); the
command is thin glue. Match `macro-research`'s exact option set + the `ai/macro/` module layout
(reader / pure aggregator / formatter).

## Testing & coverage

- **Unit tests**: table round-trips (append, per-character isolation); the recording hook fires
  on a `FightAction` **win** AND **loss** with the right `task_key`/worn-loadout/predicted/actual,
  and does NOT fire for non-fight actions; best-effort (a `SQLAlchemyError` is swallowed, no
  crash); the aggregator computes calibration + per-loadout tallies + the two mis-prediction
  buckets correctly on crafted rows; the CLI command prints/writes (typer invocation).
- **No formal lockstep** (justified carve-out — no bot decision logic; documented in
  `formal/README.md`). Full unit suite stays 100% line coverage; full `formal/gate.sh` green
  (D adds no Lean, touches no proved core).
- **No live-network test** in the suite — the hook + report are tested against crafted store
  rows, not the live server (avoids the flaky-live-test class that bit C's
  `test_gear_taxonomy_live_audit`).
- `record_*` best-effort (`SQLAlchemyError` only, never bare `Exception`).

## Out of scope / non-goals

- Changing which loadout the bot equips ("prefer learned winner" / refine-on-loss) — the
  deferred behavior-change layer D's data would feed; explicitly NOT in D.
- Recalibrating or altering `predict_win` / `is_winnable` — the kernel-proven veto is untouched.
- Gather-task outcomes — D is combat-loadout calibration; the table keys on `combat:<monster>`
  only.
- Modeling the 9 carved rune abilities (the separate "Player rune abilities" follow-on).
