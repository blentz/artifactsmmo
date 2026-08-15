# Verification harnesses read the learning store, not play-traces — design

**Date:** 2026-08-15
**Branch (proposed):** `fix/harnesses-read-the-store`
**Status:** design, pre-implementation

**Follows:** `2026-08-15-observed-craft-xp-numerator-design.md`, whose validation
harness was the first to be held to this rule.

---

## Problem

Six harnesses under `formal/diff/` measure real play to anchor claims the code
depends on. All six read `play-trace-*.jsonl`.

**Traces are a debugging artifact the user deletes at will.** 164 of 169 were
deleted on 2026-08-15, and the standing rule is that the app takes its data from
the learning store. The harnesses are not the app, but they are the *evidence
for* the app: their numbers are quoted in production docstrings and in Lean
role-theorem comments. Evidence that cannot be re-run is not evidence anyone can
check — it is a claim with a citation attached.

The app itself already honours the rule. Nothing under `src/` reads a trace at
runtime: every mention is a docstring citation, the writer in
`commands/play.py`, or the optional `stats --trace-file` flag.

### What each harness needs, measured against the `cycles` schema

| harness | needs | in the store? |
|---|---|---|
| `xp_formula_replay` | char `level`, `xp`, `action_repr` | **yes** |
| `level_cost_replay` | char `level`, `action_repr` | **yes** |
| `trace_lockstep` | `level`, `xp`, `hp` | **yes** |
| `trace_characterize` | `level`, `hp`, `xp` | **yes** |
| `craft_xp_replay` | craft xp + the skill level it was paid at | **yes**, via `craft_yield` since `f08dd5aa` |
| `gather_xp_replay` | the character's skill **levels** before the action | **no** |

`cycles` records skill *deltas* (`delta_skill_xp_json`) and never skill levels.
That is the same gap that forced the craft measurement onto traces in the first
place.

---

## Goal

Every harness re-runnable from the learning store alone, with its findings
intact or its loss of coverage stated.

### Non-goals

- **Changing what any harness concludes.** This moves the corpus, not the
  question. Where a number moves because the corpus moved, the number is
  updated; where a conclusion would move, that is a finding to report, not to
  absorb.
- **Back-filling history.** The 49,263 existing `cycles` rows were written
  without skill levels and cannot acquire them. Inventing levels would feed a
  measurement fabricated observations — the same refusal `craft_yield.skill_level`
  already makes.
- **Removing trace *writing*.** `commands/play.py` keeps producing traces; they
  remain useful for ad-hoc debugging. Only the dependency direction changes.

---

## Design

### Increment 1 — `cycles.skill_levels_json`

A nullable JSON column holding the character's skill levels **before** the
action, written one line below the existing `delta_skill_xp_json` at
`ai/player.py:3274`, where `prev_state` is already in scope:

```python
skill_levels_json=json.dumps(prev_state.skills, ensure_ascii=False, sort_keys=True),
```

One-shot `ALTER` for existing caches, matching the two migrations already in
`LearningStore.__init__`. Nullable with no default: a row without levels must
read as "unknown", never as level 0.

**Pre-action, not post-action, and this is the load-bearing detail.** The
server's `level_penalty` applies at the level held when the XP is paid. The
craft-XP work established the general form of this error the hard way — a
replay that took the *following* snapshot credited every action with its
neighbour's result and produced a table that survived three review rounds before
anyone checked it against `fight.xp`.

### Increment 2 — the four unblocked harnesses

`xp_formula_replay`, `level_cost_replay`, `trace_lockstep`, `trace_characterize`
read `cycles` instead of trace files. Each keeps its assertions and its report
file; the corpus changes from 169 files to 49,263 rows.

The record shape differs in one way that matters: a trace record carries a full
state snapshot, while a `cycles` row carries scalars plus deltas. Where a
harness reconstructed a delta by differencing snapshots, it now reads the delta
column directly — which is also how it stops being able to make the
off-by-one error described above, because the row's delta is already attributed
to the row's own action.

### Increment 3 — `craft_xp_replay` reads `craft_yield`

Its trace path is removed. `craft_yield` carries `(xp, quantity, skill_level)`
per `(character, item_code)` since `f08dd5aa`, which is what this measurement
needs. Rows with a null `skill_level` — every row written before that commit —
are excluded, not defaulted.

### Increment 4 — `gather_xp_replay`, after data accumulates

Migrates once `skill_levels_json` has rows. **Until it does, it reports that it
has no usable observations and exits non-zero rather than passing vacuously.**
A harness that silently finds nothing to check is indistinguishable from one
that checked and found nothing wrong, and this project has shipped that
confusion before.

---

## The cost, stated plainly

**`GREY_SKILL_GAP = 11`'s evidence becomes historical.** It currently rests on
3231 gathers with zero exceptions at the band boundary. Those gathers were in
the deleted traces. After this change the claim stands in the record, cited to a
measurement that cannot be re-run until the bot accumulates comparable play
under the new column.

The constant is not in doubt — it is corroborated by the doc's own prose, by
Lean's `Formal.SkillXpPositive`, and by a mutation group. What is lost is the
ability to re-derive it on demand. The honest form of that in
`skill_xp_positive.py`'s docstring is a citation that says *when* it was measured
and that the corpus behind it is gone, rather than one implying a reader can
reproduce it today.

---

## Citations that must move with the numbers

Migrating changes the corpus, so the reported figures **will** change. Every
citation of a moved figure is updated in the same commit as the harness that
moves it. Known sites:

- `src/artifactsmmo_cli/ai/skill_xp_positive.py` — the gap table and
  `GREY_SKILL_GAP`'s attribute docstring
- `src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py` — `_beats`'s
  craft-XP paragraph
- `src/artifactsmmo_cli/ai/learning/projections.py`
- `formal/Formal/XpPositive.lean`, `formal/Formal/SkillXpPositive.lean`
- the committed `formal/diff/*_report.txt` for each migrated harness

This is the branch's largest defect risk. The predecessor spent five review
rounds removing claims that had outlived the code or data beneath them — of
varied kinds, but several of them exactly this one: a figure left standing in a
docstring after the measurement under it had moved.

---

## Testing

- Each migrated harness must **run green against the real store** and have its
  report file regenerated in the same commit.
- **Each must fail loudly on an empty corpus.** A harness whose store query
  returns nothing exits non-zero with a message saying so. Verified by pointing
  it at an empty temporary DB.
- **The off-by-one guard.** Any harness that attributes an outcome to an action
  must state which record the outcome belongs to and assert it against a
  self-evident ground truth in the same row — `delta_xp` against `xp`
  progression, for instance. The craft replay's error was invisible for three
  rounds precisely because nothing asserted the attribution.
- `skill_levels_json`'s migration is verified against a **copy** of the live
  cache, as increment 1 of the craft-XP work was: rows preserved, old rows
  reading back unknown.
- Full gate green, with the bot stopped.

---

## Residuals

- **The shadow-decision gap.** `stats --trace-file` exists because the
  progression-tree shadow decision is traced-only and never persisted. This
  design does not close it; doing so needs its own column and write site.
- **Fit and check share one source.** Inherited from the craft-XP spec: a
  measurement validated against the same table it is derived from cannot catch
  an error in how that table is written.
