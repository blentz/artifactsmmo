# Rank grind rungs by observed craft XP, not by craft level — design

**Date:** 2026-08-15
**Branch (proposed):** `fix/observed-craft-xp-numerator`
**Status:** design, pre-implementation

**Follows:** `2026-08-14-grind-rung-xp-rate-ranking-design.md`, which made the
grind rank by XP-per-action and recorded this as its central residual.

---

## Problem

The grind ranks candidate rungs by `craft_level / effective_steps` — XP per
action. The numerator is a *proxy*: the server pays

```
XP = Round((XP_base + (content_level / skill_level) * k)
           * level_penalty * wisdom_bonus)
```

and `XP_base`, `k` and `wisdom_bonus` are in neither the docs nor the API. The
predecessor branch measured the proxy against real play and refuted
proportionality, leaving the direction of the error known and the fix deferred.

**The proxy is worse than "biased". It is blind to a 10× difference.** From
`craft_yield`, the table the bot already fills from the API's own `details.xp`:

| skill | craft level 1 | 5 | 10 | 15 |
|---|---|---|---|---|
| mining, woodcutting | 5 | — | 23–25 | — |
| cooking | 28 | — | — | — |
| alchemy | — | 59 | 124–125 | — |
| weaponcrafting | 53–75 | 130–131 | — | — |
| gearcrafting | 53–63 | 118–131 | — | 396 |
| jewelrycrafting | 54–63 | 123–124 | 249 | 403 |

`ash_plank` (woodcutting) and `apprentice_gloves` (weaponcrafting) are **both
craft level 1**. They pay **5** and **53**. The ranking treats them as equal
numerators. Item level equals craft level for every item checked, so this is
not a level-vs-level confusion — it is a real per-skill difference the current
key cannot represent.

**The data to fix it is already being collected.** `CraftAction` records the
API's `details.xp` into `craft_yield` after each successful craft it executes,
whenever a learning store is attached (`ai/actions/crafting.py:117-120` →
`learning/store.py:822`). 62 rows, 27 distinct items, values matching an
independent trace replay exactly (`water_bow` 131, `life_ring` 403). Nothing new
needs instrumenting to *gather* the numerator.

---

## What blocks it today

`record_craft_yield(item_code, quantity, xp)` stores no skill level, and is
last-write-wins. A stored `131` means "131 at whatever level that character had
that day", and the same item pays less as the skill rises. Two consequences:

1. **The values go stale silently.** Nothing marks a row as measured at a level
   the character has since passed.
2. **The formula cannot be fitted.** `skill_level` is a term in it. Its absence
   is also the most likely explanation for the spread *within* a level —
   gearcrafting level 1 spanning 53 to 63 — which would otherwise look like
   noise. Until the column exists, that spread cannot be attributed and the fit
   cannot be checked.

This is the same gap the predecessor branch hit from the other side: the
`cycles` table has no per-skill-level column either, which is why its craft-XP
replay had to read play-traces instead.

---

## Goal

Replace the rate's numerator with a per-skill XP model fitted to observations,
covering every recipe rather than only observed ones.

### Non-goals

- **Changing the ordering itself.** The four-level key, the `wanted` credit and
  the four filters all stay exactly as they are. Only what feeds the numerator
  changes.
- **Per-character modelling.** `wisdom_bonus` is per-character and
  unobservable; identical items differ ~±5% across characters (`copper_armor`
  118–123). That is the noise floor, not a target.
- **Retrofitting existing rows.** The 62 rows already in `craft_yield` have no
  skill level and cannot acquire one. They stay as corroboration, not as fit
  input.

---

## Design

### Increment 1 — record the skill level (independent, lands first)

`craft_yield` gains a `skill_level` column; `CraftAction` passes the crafting
skill's level at the moment it records the yield. Existing rows keep a null and
are excluded from fitting.

**This is deliberately first and deliberately alone.** It blocks nothing, and
every cycle the bot runs without it is an observation that cannot be used later.
It is also the only part of this design whose value does not depend on the fit
working.

### Increment 2 — the pure XP model

New module `ai/craft_xp_model.py`:

```python
def craft_xp(xp_base: int, k: int, craft_level: int, skill_level: int) -> int
```

implementing the published formula over integers. `level_penalty` is **not**
introduced as a new free parameter. What this repo has observed is the *band* —
crafts pay at `gap <= 10` and pay zero at or beyond `GREY_SKILL_GAP = 11`, with
no exception in 3231 gathers and 450 crafts. The model therefore treats the
penalty as **1 inside the band and 0 outside**, calling `skill_xp_positive` for
the predicate rather than restating it, so there is one grey rule in the
codebase and not two that can drift.

**That the penalty is exactly 1 inside the band is an assumption, not an
observation** — the measurements distinguish paying from not-paying, not a
graded multiplier. If it is graded, the fitted `XP_base` and `k` will absorb
some of it and the residuals will rise with the gap. The replay harness below
must therefore report residuals **bucketed by gap**, which is what would expose
a graded penalty rather than hiding it inside a constant.

Pure, integer-exact, no floats — it is a candidate for mechanical extraction on
the same terms as `_beats`.

### Increment 3 — fitting

New module fits `XP_base[skill]` and `k[skill]` by least squares over that
skill's `craft_yield` rows that carry a skill level, storing the result per
skill.

**A skill with fewer than two distinct craft levels gets no fit at all.** No
default, no borrowed constants from a neighbouring skill — the repo's rule is
"use only API data or fail with an error", and a fabricated constant here would
be exactly the kind of invisible fiction this project keeps paying for.
Current coverage: 6 of 7 skills qualify (alchemy, gearcrafting, jewelrycrafting,
mining, weaponcrafting, woodcutting); cooking has one level observed and would
get no fit today.

### Increment 4 — reaching the ranking

`GrindCandidate` gains `xp_estimate: int`, which becomes the rate numerator.

`craft_level` **stays exactly where it is** — as filter F2 (`craft_level <=
current_level`) and as the level-3 tie-break. The four filters do not move, so
the membership invariant that keeps `LevelSkill.is_applicable` and
`next_grind_goal` agreeing is untouched by construction.

Where a skill has no fit, the producer sets `xp_estimate = craft_level`. This
is a **stated fallback to the previous proxy**, written in the docstring as
such, not a silent default: the alternative — excluding unfitted skills from
the candidate set — would move membership and could stall a grind outright.

---

## Formal

`GrindCandidate`'s structure changes, so the extracted Lean regenerates and all
five ordering theorems are restated over `xp_estimate`:
`beats_prefers_higher_rate`, `beats_prefers_cheaper_at_equal_level`,
`costlier_never_beats_at_equal_level`, `beats_prefers_wanted`,
`unwanted_not_beats_wanted`.

Their proofs are expected to survive nearly unchanged, because they reason
about the numerator as an integer and not about `craft_level` meaning a craft
level — but that expectation is from reading their statements, not from
attempting the port.
**If a proof needs real work, that is a signal the change is not as contained as
this section claims** — report it rather than forcing it.

The filter and fold theorems must again come through untouched. That they did
so on the predecessor branch is the evidence the filter set is the right cut;
the same must hold here.

If `craft_xp_model.craft_xp` is extracted, it needs its own role theorem —
minimally, that it returns 0 exactly when `skill_xp_positive` is false, which
is the property the grey filter depends on.

---

## Testing

**The fit must be validated before it is allowed to displace the proxy.** A
fitted curve is the easiest thing yet to assert falsely, and the predecessor
branch's entire defect history was verification claiming more than the data
supports. So:

- A replay harness in `formal/diff/` predicts each observation from its skill's
  fitted parameters and reports residuals per skill. It prints the table
  whatever the outcome.

  **It reads the learning store, not `play-trace-*.jsonl`.** Traces are a
  debugging artifact the user deletes at will — 164 of 169 went on 2026-08-15 —
  and nothing the app or its evidence depends on may be built on them. The
  observations this harness validates against are `craft_yield` rows, which is
  where they already live. `formal/diff/craft_xp_replay.py`, written on the
  trace corpus, is therefore **superseded** by that harness rather than
  extended: its verdict stands in the record, but a trace-based measurement
  cannot be re-run on demand and so cannot be the thing a fit is checked
  against.
- The spec's acceptance bar: **the fit's median absolute error must be at or
  below the ±5% cross-character spread already observed on identical items.**
  Below that is noise the model cannot beat, because `wisdom_bonus` is
  unobservable. A fit that cannot reach it does not ship, and the numerator
  stays `craft_level` for that skill.
- The harness must state its own coverage — how many observations, how many
  skills, how many distinct levels per skill — so a thin fit is visible as thin.

**Discrimination, proven both ways.** A unit test must show a selection that
differs from the `craft_level` numerator, and must fail when the numerator is
reverted. The predecessor branch shipped 14 tests that could not see its change;
that must not recur.

**The `ash_plank` / `apprentice_gloves` case is the acceptance test.** Both are
craft level 1; they pay 5 and 53. A weaponcrafting grind choosing between rungs
of comparable cost must prefer the one that actually pays, and under the old
numerator it could not tell them apart.

**Live acceptance.** As before: a real character's selection, read through the
production path with a real `SelectionContext`, not a fixture.

---

## Risks

- **A bad fit is invisible.** Mitigated by the replay harness and the stated
  accuracy bar, and by keeping the `craft_level` fallback so a refused fit
  degrades to today's behaviour rather than to nothing.
- **The formula's shape may not fit.** The published form is assumed correct;
  only its constants are fitted. If residuals stay large with sensible
  constants, the shape is wrong and this design is refuted — which the harness
  will show, and which is a result worth having rather than a failure to hide.
- **Increment 1's data takes time to accumulate.** The fit cannot be validated
  the day the column lands. This is why the increments are separable and why
  the column goes first.
- **The trace corpus is not a dependency and must not become one.** The user
  deleted 164 of 169 `play-trace-*.jsonl` files on 2026-08-15, and the standing
  rule is that the app takes its data from the learning store. The app already
  honours this — nothing under `src/` reads a trace at runtime; every mention
  is a docstring citation, the writer in `commands/play.py`, or the optional
  `stats --trace-file` flag. This design keeps to it: the observations, the
  fit, and the validation all read `craft_yield`.

  What this costs is the *independent* cross-check the traces provided. The
  fit and the data it is checked against now come from the same table, so an
  error in how `CraftAction` records a yield would be invisible to the
  harness. The mitigation is that `craft_yield` is written straight from the
  API's own `details.xp` with no derivation in between — there is little room
  between the server's number and the stored one — but it is a weaker
  arrangement than two independent sources and is named as such rather than
  glossed.

---

## Residuals inherited, not addressed here

- Cross-character `wanted` from sibling supply demand still has no live
  verification.
- The `wanted` credit remains a total pivot over the reachable domain; narrowing
  it to the committed target rather than the whole near-term set is a separate
  follow-up.
