# Grind Rung XP-Rate Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the skill grind pick the rung that pays the most skill XP per action, instead of the rung with the cheapest chain, and revive the `wanted` key that has been dead in production since it was written.

**Architecture:** The pure decision core `_beats` stops ordering on `acquire_steps` ascending and starts ordering on `craft_level / effective_steps` descending, compared by integer cross-multiplication so the core stays float-free and extractable to Lean. `effective_steps` is `0` for a rung the objective already wants (its chain is work owed regardless, so the grind's marginal cost for it is zero), with `wanted`, `craft_level` and raw `acquire_steps` as tie-breaks under the rate. Separately, the `wanted` flag is wired to a `SelectionContext` for the first time, applied *after* the candidate cache so the cache key stays context-free.

**Tech Stack:** Python 3.13, `uv`, pytest, Lean 4 + Mathlib (`formal/`), mechanical Python→Lean extraction (`scripts/extract_lean.py`), Hypothesis differential harnesses, mutation testing (`formal/diff/mutate.py`).

**Spec:** `docs/superpowers/specs/2026-08-14-grind-rung-xp-rate-ranking-design.md`

## Global Constraints

- Every Python command runs through `uv run`. `unset VIRTUAL_ENV` first if the shell has one. `uv` is at `/home/blentz/.local/bin/uv`.
- **Never** `git add -A` — the repo contains a `formal/.lake` symlink to a shared 9.3 GB cache.
- **Never** `git checkout <path>` or `git stash` to undo a probe. Both have destroyed uncommitted work in this repo. Copy the file aside with `cp` and copy it back.
- **Never** pipe `formal/gate.sh` into `tail` — a visible `GATE FAIL` was once read as `rc=0`. Redirect to a file, or use `${PIPESTATUS[0]}`.
- **Never** run `formal/gate.sh` or `formal/diff/mutate.py` concurrently with anything importing `src/`, including the live bot.
- **Never** use `--no-verify`.
- Imports go at the top of the file. No inline imports. No `if TYPE_CHECKING`. No `except Exception`.
- One *behavioral* class per file. Pure data/schema/enum groups may share a module.
- Success criteria for the suite: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- Do not run the full `tests/` suite in a task — it takes ~17 minutes on the parallel runner and has cost this project two lost agents. Run the named test files.
- Mutation anchors must resolve to **exactly one** site, and must be refreshed in the same commit as the code edit.
- Non-vacuity: every new Lean theorem's witness uses distinct nonzero values. An all-zeros witness has passed this gate before while proving nothing.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py` | The pure ordering core. `_beats` gains the rate comparison and the credit. | 1 |
| `formal/Formal/Extracted/SkillGrindSelection.lean` | Mechanically regenerated. Never hand-edited. | 1 |
| `tests/test_ai/test_skill_grind_selection.py` | Unit tests for the core, incl. the new discriminating case. | 1 |
| `formal/Formal/SkillGrindSelection.lean` | Hand-written role theorems over the extracted def. | 2 |
| `formal/diff/mutate.py` | Mutation anchors for `_beats`. | 2 |
| `src/artifactsmmo_cli/ai/tiers/skill_grind_target.py` | Impure producer. Gains a `ctx` parameter and post-cache `wanted`. | 3 |
| `src/artifactsmmo_cli/ai/level_skill_expand.py` | Passes its existing `ctx` down to the selector. | 3 |
| `tests/test_ai/test_skill_grind_target.py` | Wiring tests: `wanted` live, cache stays context-free. | 3 |
| `formal/diff/craft_xp_replay.py` | New. Measures whether XP is proportional to `craft_level`. | 4 |

---

### Task 1: The rate ranking in the pure core

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py:47-92` (`_beats`)
- Modify (regenerate, never by hand): `formal/Formal/Extracted/SkillGrindSelection.lean`
- Test: `tests/test_ai/test_skill_grind_selection.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `_beats(c: GrindCandidate, best: GrindCandidate | None) -> bool` with the four-level order below. `GrindCandidate`'s fields are unchanged: `code: str`, `craft_skill: str`, `craft_level: int`, `acquire_steps: int`, `obtainable: bool`, `wanted: bool`, `xp_positive: bool`.

**Background you need.** `_beats` is one of two functions in this file that are **mechanically extracted to Lean** (`scripts/extract_lean.py:451-454` names `_beats` and `skill_grind_selection_pure`). The generated file carries a sha256 of the Python source and `formal/gate/check_extraction.sh` fails if they drift. So: no floats (the Lean side is `Int`), no calls to module-level helpers (only these two functions are extracted — a helper call would not resolve), and you must regenerate in this same task. Local `let` bindings and conditional expressions both extract fine; the existing generated file already contains `let` bindings.

- [ ] **Step 1: Write the discriminating failing test**

Add to `tests/test_ai/test_skill_grind_selection.py`. The file already has a `_c` helper at line 9 with signature `_c(code, skill="weaponcrafting", level=1, steps=0, obtainable=True, wanted=False, xp_positive=True)` — use it.

```python
def test_a_costlier_chain_wins_when_it_pays_proportionally_more_xp():
    """THE 2026-08-14 SYMPTOM. Live Lor, weaponcrafting 8: apprentice_gloves
    priced 13 actions at craft level 1 (rate 0.077) and sticky_dagger priced 59
    at craft level 5 (rate 0.085). Cheapest-chain picked the gloves, and the
    grind sat at weaponcrafting 8 for 757 cycles crafting a level-1 rung.

    This is the ONLY test in the file that distinguishes the two orderings.
    Every other cost-versus-level case here uses a `steps=0` candidate (free
    wins under both) or an example where the cheaper rung is also the
    higher-rate one -- including the 2026-08-06 regression guard. Verified by
    working all 14 through both orderings by hand while planning this change.
    """
    cands = [_c("apprentice_gloves", level=1, steps=13),
             _c("sticky_dagger", level=5, steps=59)]
    assert skill_grind_selection_pure("weaponcrafting", 8, cands) == "sticky_dagger"


def test_a_wanted_rung_wins_on_rate_because_its_chain_is_owed_anyway():
    """A wanted rung's chain is work the objective owes regardless of the
    grind, so the grind's MARGINAL cost for it is zero -- it wins the rate
    comparison rather than winning by lexicographic fiat. 500 steps against 2
    is the shape that would look absurd under raw cost and is correct under
    marginal cost."""
    cands = [_c("throwaway", level=5, steps=2, wanted=False),
             _c("committed_weapon", level=1, steps=500, wanted=True)]
    assert skill_grind_selection_pure("weaponcrafting", 8, cands) == "committed_weapon"


def test_raw_cost_still_separates_two_rungs_the_objective_both_wants():
    """The credit zeroes effective steps for EVERY wanted rung, so they all tie
    on rate. Two rungs both owed are not equally near -- the cheaper is reached
    sooner -- so RAW acquire_steps is the final tie-break. Without it this falls
    through to insertion order, which is arbitrary."""
    cands = [_c("owed_far", level=3, steps=40, wanted=True),
             _c("owed_near", level=3, steps=4, wanted=True)]
    assert skill_grind_selection_pure("weaponcrafting", 8, cands) == "owed_near"


def test_a_free_throwaway_does_not_tie_its_way_past_a_wanted_keeper():
    """Both credit to zero effective steps, so the RATE comparison ties at
    zero. Without `wanted` as the first tie-break under the rate, the incumbent
    survives on insertion order -- which is the June 2026
    apprentice_gloves-over-copper_dagger inversion returning through the back
    door."""
    cands = [_c("free_throwaway", level=1, steps=0, wanted=False),
             _c("copper_dagger", level=1, steps=2, wanted=True)]
    assert skill_grind_selection_pure("weaponcrafting", 8, cands) == "copper_dagger"
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
uv run pytest tests/test_ai/test_skill_grind_selection.py -v -k "costlier_chain or owed_anyway or both_wants or past_a_wanted_keeper"
```

Expected: `test_a_costlier_chain_wins_when_it_pays_proportionally_more_xp` FAILS with `assert 'apprentice_gloves' == 'sticky_dagger'`, and `test_raw_cost_still_separates_two_rungs_the_objective_both_wants` PASSES already (the old key ranks on raw cost too). The other two pass under the old lexicographic `wanted`. **That one failing test is the whole discriminating surface** — record which ones failed in your report.

- [ ] **Step 3: Replace `_beats`**

Replace the body of `_beats` (keep the function name and signature). The `if best is None: return True` line must stay first — the extractor turns it into the Lean `match`, and the local bindings below it land inside the `some` branch.

```python
def _beats(c: GrindCandidate, best: GrindCandidate | None) -> bool:
    """True when feasible `c` strictly precedes `best` in the selection order

        (craft_level / effective_steps  desc,   # XP-proxy per action
         wanted                         desc,   # keeper breaks a rate tie
         craft_level                    desc,
         acquire_steps                  asc)    # real cost breaks the rest

    where `effective_steps` is 0 for a wanted rung and `acquire_steps`
    otherwise. A None `best` (no incumbent) is always beaten. A full tie keeps
    the incumbent (first-seen in candidate order) — deterministic without a
    string tie-break.

    RATE, NOT COST (2026-08-14). The first key was `acquire_steps` ascending —
    cheapest chain wins — and cheapness is anti-correlated with the thing a
    grind exists to produce: the cheapest in-level rung is the LOWEST-level
    one, which pays the least xp per craft. So the ranking optimised against
    its own purpose. Live Lor and HAL, both at the same moment: Lor picked
    `apprentice_gloves` (craft level 1, 13 actions) over `sticky_dagger` (5,
    59), HAL picked the same gloves (43 actions) over `water_bow` (5, 59), and
    Lor's weaponcrafting sat at 8 across 757 grind cycles. Under rate the
    order inverts — 5/59 = 0.085 beats 1/13 = 0.077 — while the 2026-08-06
    R2D2 case is UNCHANGED, because there the cheaper rung was also the faster
    one (1/7 = 0.143 against 5/51 = 0.098).

    CROSS-MULTIPLIED, NOT DIVIDED. `c.craft_level * best_steps` against
    `best.craft_level * c_steps` is the same comparison in integers. This core
    is mechanically extracted to Lean over `Int` (`scripts/extract_lean.py`),
    so a float would not survive the trip, and the cross product also disposes
    of the zero-denominator case without a special branch: a rung at zero
    effective steps makes the opposing product zero and wins on any positive
    level, with two such rungs falling through to the tie-breaks.

    `craft_level` IS A PROXY FOR XP, NOT XP. The server pays
    `Round((XP_base + (content_level / skill_level) * k) * level_penalty *
    wisdom_bonus)` and neither `XP_base` nor `k` is published or in the API
    (`ai/skill_xp_positive`). At a fixed skill level xp is monotone
    nondecreasing in content level, which justifies `craft_level` as an
    ORDINAL proxy; using it as the CARDINAL numerator of a ratio additionally
    assumes xp is proportional to it, and `level_penalty` varies across rungs
    by a factor nobody has measured. The assumption is named here rather than
    hidden: see `formal/diff/craft_xp_replay.py` for what the play-traces say
    about it.

    WANTED IS A MARGINAL-COST CREDIT, NOT A PIVOT. A rung the objective
    already wants is work the character owes regardless of the grind, so the
    grind's marginal cost for it is zero — hence `effective_steps = 0` rather
    than a key above the rate. Crafting a wanted item gains the SAME skill xp
    and yields a keeper instead of a throwaway (2026-06-24: pure cheapest-chain
    greed made the bot craft a value-10 `apprentice_gloves` while ignoring the
    committed value-83 `copper_dagger`). Expressing that as a credit rather
    than a lexicographic pivot is what stops a wanted rung at 500 steps
    outranking a throwaway at 2 by fiat while still letting it win on merit —
    and it keeps every term in one currency, which is the argument
    `ai/skill_grind_cost_core` already makes.

    The `wanted` tie-break is spelled as two `and`/`not` branches rather than
    `if c.wanted != best.wanted: return c.wanted`: the extractor's v1 subset
    rejects `!=` on `Bool`, and this is the shape this function already
    extracted for two years. Semantically identical.

    WHY THERE ARE STILL TWO TIE-BREAKS UNDER THE CREDIT. Crediting to zero
    makes every wanted rung tie every other wanted rung on rate, which destroys
    the cost signal among them — two rungs both owed are not equally near, so
    RAW `acquire_steps` is the last key. And a free throwaway also credits to
    zero, ties a wanted keeper at rate zero, and would survive on insertion
    order — the 2026-06-24 inversion through the back door — so `wanted` is the
    first tie-break under the rate. Neither is decoration; each closes a case
    the credit alone gets wrong.

    HISTORY. This is the fourth attempt at this ordering. `wanted`
    (2026-06-24), the `xp_positive` FILTER (2026-08-05, live Robby, 288
    zero-xp cycles), and `acquire_steps` replacing a one-level `mats_missing`
    count (2026-08-06, live R2D2, 129 cycles) were each real, and each was
    another key bolted onto a first key that was lying about what a grind is
    for. This one replaces that first key.
    """
    if best is None:
        return True
    c_steps = 0 if c.wanted else c.acquire_steps
    best_steps = 0 if best.wanted else best.acquire_steps
    c_rate = c.craft_level * best_steps
    best_rate = best.craft_level * c_steps
    if c_rate != best_rate:
        return c_rate > best_rate
    if c.wanted and not best.wanted:
        return True
    if best.wanted and not c.wanted:
        return False
    if c.craft_level != best.craft_level:
        return c.craft_level > best.craft_level
    if c.acquire_steps != best.acquire_steps:
        return c.acquire_steps < best.acquire_steps
    return False
```

Also update the `GrindCandidate.acquire_steps` field docstring (line 34-37), which currently ends "It replaced a one-level `mats_missing` count on 2026-08-06 — see `_beats`." Append: `As of 2026-08-14 it is the DENOMINATOR of a rate rather than the first ranking key, and a wanted rung credits it to zero — see `_beats`.`

- [ ] **Step 4: Run the whole selection test file**

```bash
uv run pytest tests/test_ai/test_skill_grind_selection.py -v
```

Expected: all 18 PASS (14 pre-existing + 4 new). If any pre-existing test fails, **stop and report** — the plan's analysis says all 14 pass under both orderings, and a failure means either the analysis or the implementation is wrong. Do not edit a pre-existing test to make it pass.

- [ ] **Step 5: Prove the discriminating test discriminates (the ablation)**

Copy the file aside first — **not** `git stash`, **not** `git checkout`:

```bash
cp src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py /tmp/sgs.py.keep
```

Now temporarily revert just the ordering by putting the old two keys back at the top of the comparison chain (leave the docstring alone), run, then restore:

```bash
# edit _beats so the first two comparisons are again:
#     if c.wanted and not best.wanted: return True
#     if best.wanted and not c.wanted: return False
#     if c.acquire_steps != best.acquire_steps:
#         return c.acquire_steps < best.acquire_steps
uv run pytest tests/test_ai/test_skill_grind_selection.py -v 2>&1 | tail -30
cp /tmp/sgs.py.keep src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py
uv run pytest tests/test_ai/test_skill_grind_selection.py -q 2>&1 | tail -3
```

Expected: with the old ordering, `test_a_costlier_chain_wins_when_it_pays_proportionally_more_xp` FAILS; after restoring, everything passes. **Paste both outputs into your report.** A predecessor branch shipped a fix whose test stayed green with the defect reinstated; this step is the guard against repeating that.

- [ ] **Step 6: Rewrite the test that now asserts a falsehood**

`test_craft_level_is_only_a_tie_break_under_cost` (line 126) passes under both orderings while its name and comment assert "A higher craft_level is preferred ONLY when the chains cost the same." That is no longer true. Replace the whole test:

```python
def test_craft_level_buys_its_way_past_a_cheaper_chain_only_by_paying_for_it():
    # A higher craft_level DOES outrank a cheaper chain now -- but only when it
    # pays proportionally more per action. This test replaced
    # `test_craft_level_is_only_a_tie_break_under_cost` on 2026-08-14: that test
    # passed under both orderings while asserting the opposite of what the code
    # does, which is worse than failing.
    # 5/51 = 0.098 loses to 1/7 = 0.143 -- the level does NOT buy its way past.
    loses = [_c("cheap_low", level=1, steps=7), _c("dear_high", level=5, steps=51)]
    assert skill_grind_selection_pure("weaponcrafting", 15, loses) == "cheap_low"
    # 5/20 = 0.250 beats 1/7 = 0.143 -- same level gap, cheaper enough to win.
    wins = [_c("cheap_low", level=1, steps=7), _c("dear_high", level=5, steps=20)]
    assert skill_grind_selection_pure("weaponcrafting", 15, wins) == "dear_high"
    # equal cost -> the level tie-break, unchanged.
    tied = [_c("low", level=1, steps=7), _c("high", level=5, steps=7)]
    assert skill_grind_selection_pure("weaponcrafting", 15, tied) == "high"
```

Also update `test_among_wanted_fewest_missing_still_wins`'s comment (line 36), which says "among equally-wanted, the old (fewest-missing, level) key still applies" — the assertion is still correct but the reason changed. Replace the comment with: `# Among equally-wanted, every rate ties (the credit zeroes them all), so the` / `# final RAW acquire_steps tie-break decides. Same answer, different reason.`

- [ ] **Step 7: Run the file again**

```bash
uv run pytest tests/test_ai/test_skill_grind_selection.py -v
```

Expected: 18 passed.

- [ ] **Step 8: Regenerate the extracted Lean**

```bash
uv run python scripts/extract_lean.py
git diff --stat formal/Formal/Extracted/SkillGrindSelection.lean
```

Expected: the file changes (new sha256 header, new `_beats` body with `let` bindings and `*`). If the extractor **errors**, stop and report the exact message — do not hand-edit the generated file, and do not work around it by restructuring `_beats` without saying so.

Then confirm the drift gate agrees:

```bash
bash formal/gate/check_extraction.sh > /tmp/extract.txt 2>&1; echo "rc=$?"; tail -5 /tmp/extract.txt
```

Expected: `rc=0`.

- [ ] **Step 9: Run the neighbours that consume this core**

```bash
uv run pytest tests/test_ai/test_skill_grind_target.py tests/test_ai/test_level_skill_expand.py -q 2>&1 | tail -5
```

Expected: pass. If a test here fails, it is a real behaviour change in a consumer — report it, do not rebaseline it.

- [ ] **Step 10: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py \
        tests/test_ai/test_skill_grind_selection.py \
        formal/Formal/Extracted/SkillGrindSelection.lean
git commit -m "fix(ai): the grind ranked by cheapest chain, which is anti-correlated with xp

The cheapest in-level rung is the lowest-level one, which pays the least skill
xp per craft, so the first ranking key optimised against the grind's purpose.
Live Lor and HAL both picked apprentice_gloves (craft level 1) over a level-5
rung; Lor's weaponcrafting sat at 8 across 757 grind cycles.

_beats now orders on craft_level / effective_steps, cross-multiplied so the
core stays integer-exact for extraction, with wanted crediting effective_steps
to zero (a wanted rung's chain is owed regardless, so its marginal cost to the
grind is zero). wanted, craft_level and raw acquire_steps break ties under it.

The 2026-08-06 R2D2 guard is unchanged -- there the cheaper rung was also the
faster one. Ablation proved the new test fails with the old ordering."
```

---

### Task 2: Lean role theorems and mutation anchors

**Files:**
- Modify: `formal/Formal/SkillGrindSelection.lean:271-317` (replace `beats_prefers_cheaper_chain`)
- Modify: `formal/diff/mutate.py:1351-1418` (`SKILL_GRIND_SELECTION_MUTATIONS`)

**Interfaces:**
- Consumes: the extracted `Extracted.SkillGrindSelection._beats` regenerated in Task 1, whose Lean fields are `craft_level : Int`, `acquire_steps : Int`, `wanted : Bool`.
- Produces: theorems `beats_prefers_higher_rate`, `beats_prefers_cheaper_at_equal_level`, `beats_prefers_wanted`.

**Background.** `beats_prefers_cheaper_chain` (line 271) states "among candidates of equal `wanted` standing, a STRICTLY CHEAPER chain always beats a costlier incumbent — regardless of craft level". Task 1 makes that **false on purpose**. Its docstring calls itself "THE ROLE THAT WOULD HAVE CAUGHT ALL THREE RECURRENCES", so it is replaced by three theorems, not deleted. Every other theorem in the file (`grind_actionable`, `fold_reaches_some`, `fold_some_feasible`, `step_preserves_some`, `step_feasible_some`, `result_feasible`, `guard_false_feasible`, `step_cases`, `unfold_select`) is about the **filters** and the fold's shape; the filters do not move, so all of them must stay green **unedited**. If one needs editing, that is evidence against the spec's filter audit — report it rather than patching it.

- [ ] **Step 1: Replace the falsified theorem**

Delete `beats_prefers_cheaper_chain` and its doc comment (lines 271-317, to end of file) and put this in its place:

```lean
/-- `beats_prefers_higher_rate`: between two UNWANTED candidates, a strictly
higher xp-per-action rate wins — cross-multiplied, so no division and no
zero-denominator case.

THIS REPLACES `beats_prefers_cheaper_chain`, which said the strictly CHEAPER
chain always wins regardless of craft level. That was true of the ordering
until 2026-08-14 and is now false on purpose: cheapness is anti-correlated with
xp, because the cheapest in-level rung is the lowest-level one. Live Lor picked
a 13-action level-1 rung over a 59-action level-5 rung and sat at weaponcrafting
8 for 757 grind cycles. The surviving content of the old theorem is
`beats_prefers_cheaper_at_equal_level` below.

STATED FOR THE UNWANTED PAIR, deliberately. Two WANTED candidates both credit to
zero effective steps and therefore tie on rate by construction, so quantifying
this over equal-`wanted` pairs generally would be vacuously satisfied on half
its domain — the shape of hypothesis this project has shipped before while
proving nothing. -/
theorem beats_prefers_higher_rate (c b : GrindCandidate)
    (hcw : c.wanted = false) (hbw : b.wanted = false)
    (hrate : c.craft_level * b.acquire_steps > b.craft_level * c.acquire_steps) :
    _beats c (some b) = true := by
  have hne : ¬ (c.craft_level * b.acquire_steps = b.craft_level * c.acquire_steps) := by
    omega
  simp [_beats, hcw, hbw, hne, hrate]

/-- `beats_prefers_cheaper_at_equal_level`: at equal `wanted` standing and EQUAL
`craft_level`, the strictly cheaper chain still wins.

This is what survives of `beats_prefers_cheaper_chain`, and stating it
separately keeps the anti-regression guarantee that theorem was carrying:
cheapness still decides wherever it is the only thing that differs. It holds by
two different routes, which is why it is worth proving rather than assuming —
for an unwanted pair through the rate itself (equal levels make the rate
comparison a comparison of steps), and for a wanted pair through the final
tie-break (the credit ties their rates at zero). -/
theorem beats_prefers_cheaper_at_equal_level (c b : GrindCandidate)
    (hw : c.wanted = b.wanted) (hlvl : c.craft_level = b.craft_level)
    (hcost : c.acquire_steps < b.acquire_steps) :
    _beats c (some b) = true := by
  cases hcw : c.wanted <;> simp [_beats, hcw, hw ▸ hcw, hlvl, hcost] <;> omega

/-- `beats_prefers_wanted`: a WANTED candidate beats an UNWANTED incumbent.

The June 2026 guarantee — pure cheapest-chain greed had the bot craft a value-10
`apprentice_gloves` while ignoring the committed value-83 `copper_dagger`.

DERIVED, NOT ASSERTED, since 2026-08-14. `wanted` is no longer a key above the
rate; it credits `effective_steps` to zero, which zeroes the INCUMBENT's
cross-product, so the wanted candidate either wins the rate outright or ties it
at zero and wins the `wanted` tie-break underneath. Proving it is the check that
the credit and the tie-break together reproduce what the old lexicographic pivot
gave by fiat. -/
theorem beats_prefers_wanted (c b : GrindCandidate)
    (hcw : c.wanted = true) (hbw : b.wanted = false)
    (hlvl : 0 ≤ c.craft_level) (hsteps : 0 ≤ b.acquire_steps) :
    _beats c (some b) = true := by
  simp [_beats, hcw, hbw]
  omega
```

- [ ] **Step 2: Build Lean and repair the proofs**

```bash
cd formal && lake build 2>&1 | tail -40; cd ..
```

The three proof scripts above are written against the expected shape of the regenerated `_beats` and **may not close as written** — `simp` normalises `Bool`/`decide` differently depending on how the extractor emits the `let` bindings. Repairing them is expected work, not a sign the statements are wrong. Use `lean_goal` / `lean_diagnostic_messages` to see the actual goal. **Do not weaken a theorem's statement to make it close** — if a statement cannot be proved, that is a finding about the design and you report it.

Expected when done: `lake build` succeeds with no `sorry` and no errors.

- [ ] **Step 3: Check for sorries and axioms**

```bash
bash formal/gate/check_no_sorry.sh > /tmp/sorry.txt 2>&1; echo "rc=$?"; tail -3 /tmp/sorry.txt
bash formal/gate/check_axioms.sh > /tmp/axioms.txt 2>&1; echo "rc=$?"; tail -3 /tmp/axioms.txt
```

Expected: `rc=0` for both.

- [ ] **Step 4: Update the mutation anchors**

In `formal/diff/mutate.py`, `SKILL_GRIND_SELECTION_MUTATIONS` (starts line 1351) has four `_beats` entries whose anchor strings no longer exist in the source: `_beats cheapest-chain flip`, `_beats craft_level outranks chain cost`, `_beats drop wanted preference`, `_beats invert wanted shield`. The four filter-guard entries above them use `_GRIND_GUARD` and are unaffected — leave those alone.

**Correction to this step, ruled during Task 1.** `scripts/extract_lean.py`
rejects `!=` on `Bool`, so the `wanted` tie-break is written as two `and`/`not`
branches — the shape the function already used. Two consequences: the existing
anchors `_beats drop wanted preference` and `_beats invert wanted shield` still
resolve verbatim and are **kept**, and only the other two are replaced. Their
*comments* are now wrong, though — those two lines are a tie-break under the
rate now, not the primary key — so rewrite both comments while leaving both
anchor strings byte-identical.

Replace the two entries `_beats cheapest-chain flip` and `_beats craft_level
outranks chain cost` with these three:

```python
    # THE 2026-08-14 REGRESSION: flip the rate comparison so the WORST
    # xp-per-action rung wins. Killed by
    # test_a_costlier_chain_wins_when_it_pays_proportionally_more_xp.
    ("skill_grind_selection: _beats rate comparison flipped",
     "        return c_rate > best_rate\n",
     "        return c_rate < best_rate\n"),
    # Back to cheapest-chain: drop the numerator so the comparison degenerates
    # to steps alone. This is the pre-2026-08-14 ordering, the one that left
    # live Lor at weaponcrafting 8 for 757 cycles.
    ("skill_grind_selection: _beats back to cheapest chain",
     "    c_rate = c.craft_level * best_steps\n"
     "    best_rate = best.craft_level * c_steps\n",
     "    c_rate = best_steps\n"
     "    best_rate = c_steps\n"),
    # Drop the wanted CREDIT on the challenger -- a wanted rung is priced at
    # its full chain again, so a committed keeper loses to any cheaper
    # throwaway. Killed by
    # test_a_wanted_rung_wins_on_rate_because_its_chain_is_owed_anyway.
    ("skill_grind_selection: _beats drops the wanted credit",
     "    c_steps = 0 if c.wanted else c.acquire_steps\n",
     "    c_steps = c.acquire_steps\n"),
    # Drop the final RAW-cost tie-break -- every wanted rung ties every other
    # on rate (they all credit to zero), so without this the choice among them
    # falls to insertion order. Killed by
    # test_raw_cost_still_separates_two_rungs_the_objective_both_wants.
    ("skill_grind_selection: _beats drops the raw-cost tie-break",
     "    if c.acquire_steps != best.acquire_steps:\n"
     "        return c.acquire_steps < best.acquire_steps\n",
     "    if c.acquire_steps != best.acquire_steps:\n"
     "        return c.acquire_steps > best.acquire_steps\n"),
```

And rewrite the comments on the two KEPT entries, leaving their anchor strings
untouched. `_beats drop wanted preference` becomes:

```python
    # Neuter the wanted TIE-BREAK: a free throwaway ties a wanted keeper at rate
    # zero (both credit to zero effective steps) and then survives on insertion
    # order -- the 2026-06-24 apprentice_gloves-over-copper_dagger inversion,
    # returning through the back door under the rate ordering. Killed by
    # test_a_free_throwaway_does_not_tie_its_way_past_a_wanted_keeper.
```

and `_beats invert wanted shield` becomes:

```python
    # Invert the wanted shield: an UNWANTED candidate displaces a wanted
    # incumbent on a rate tie. Same tie-break, opposite direction. Killed by the
    # wanted-first scenarios (the winner flips off the keeper).
```

- [ ] **Step 5: Verify every anchor resolves to exactly one site**

```bash
uv run python formal/diff/mutate.py --check-anchors 2>&1 | tail -20
```

Expected: no error. An anchor that matches zero or two sites is a hard failure — `c_steps` and `best_steps` are deliberately named differently so their credit lines are distinguishable.

- [ ] **Step 6: Run the mutation group**

```bash
uv run python formal/diff/mutate.py --group skill_grind_selection 2>&1 | tail -20
```

(If `--group` is not the flag this script takes, run `uv run python formal/diff/mutate.py --help` and use the equivalent; do not run the whole mutation suite, which is long.)

Expected: every mutant KILLED. A SURVIVED mutant means a test is missing for that behaviour — add it rather than deleting the mutant.

- [ ] **Step 7: Run the differential harness**

```bash
uv run pytest formal/diff/test_skill_grind_selection_diff.py -q 2>&1 | tail -5
```

Expected: pass. This harness is property-based over random candidate lists (`max_examples=400`, biased toward feasible so the ordering keys are actually exercised), so it picks up the new ordering automatically via the regenerated oracle — but it has no case that *guarantees* the two orderings differ. Add one:

```python
def test_rate_beats_cheapest_chain_diff():
    """A case where the pre-2026-08-14 ordering and the current one DISAGREE,
    pinned against Lean. Live Lor at weaponcrafting 8: the 13-action level-1
    rung is cheaper, the 59-action level-5 rung pays more per action."""
    cands = [
        ("apprentice_gloves", "weaponcrafting", 1, 13, True, False, True),
        ("sticky_dagger", "weaponcrafting", 5, 59, True, False, True),
    ]
    py = skill_grind_selection_pure(
        "weaponcrafting", 8, [GrindCandidate(*c) for c in cands])
    lean = run_oracle("skill_grind_selection", [_args("weaponcrafting", 8, cands)])[0]
    assert py == "sticky_dagger"
    assert py == lean["code"]
```

- [ ] **Step 8: Re-run the harness**

```bash
uv run pytest formal/diff/test_skill_grind_selection_diff.py -q 2>&1 | tail -5
```

Expected: pass, one more test than before.

- [ ] **Step 9: Commit**

```bash
git add formal/Formal/SkillGrindSelection.lean formal/diff/mutate.py \
        formal/diff/test_skill_grind_selection_diff.py
git commit -m "proof(grind): restate the cheapest-chain theorem as three rate theorems

beats_prefers_cheaper_chain asserted that a strictly cheaper chain always wins
regardless of craft level. The rate ordering makes that false on purpose, so it
is replaced rather than deleted:

  beats_prefers_higher_rate            -- the new first key, stated for the
                                          unwanted pair because two wanted
                                          candidates tie on rate by construction
  beats_prefers_cheaper_at_equal_level -- what survives: cheapness still decides
                                          where it is the only difference
  beats_prefers_wanted                 -- the June 2026 guarantee, now DERIVED
                                          from the credit plus the tie-break
                                          rather than asserted by a pivot

Every filter and fold theorem is untouched and still green, which is the check
on the spec's claim that the filter set does not move.

Five mutation anchors replace four; the two credit lines are named c_steps and
best_steps so each resolves to exactly one site."
```

---

### Task 3: Wire `wanted` to a SelectionContext so it can fire

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/skill_grind_target.py` (imports, `build_selectable_grind_candidates`, `skill_grind_target`)
- Modify: `src/artifactsmmo_cli/ai/level_skill_expand.py:82-83`
- Test: `tests/test_ai/test_skill_grind_target.py`

**Interfaces:**
- Consumes: `_beats`'s use of `GrindCandidate.wanted` from Task 1.
- Produces:
  - `build_selectable_grind_candidates(skill: str, state: WorldState, game_data: GameData, ctx: SelectionContext = NO_PROFILE_CONTEXT) -> list[GrindCandidate]`
  - `skill_grind_target(skill: str, state: WorldState, game_data: GameData, reserved: frozenset[str] = frozenset(), ctx: SelectionContext = NO_PROFILE_CONTEXT) -> str | None`

**Background.** `GrindCandidate` is constructed in exactly one place in `src/` (`skill_grind_target.py:268`) and that construction passes the literal `wanted=False`. So the key has never been able to fire in production. `SelectionContext` (in `ai/selection_context.py`) already carries everything needed: `near_term_targets: frozenset[str]` (usable-now gear ∪ tool targets) and `supply_target: tuple[str, int, int] | None` whose element 0 is the item code a sibling needs. `NO_PROFILE_CONTEXT` has both empty/None, so every caller that does not pass a `ctx` keeps today's behaviour exactly.

Two hard constraints:

1. **Membership must not move.** `LevelSkill.is_applicable` (`ai/actions/level_skill.py:68`) calls `skill_grind_target` with no context and asks only `is not None`; `level_skill_expand.next_grind_goal` calls it with context. If a context-dependent term could empty the candidate set, the two walks would disagree about whether a grind exists at all — the selection-says-yes/emission-says-no split behind the wool livelock. `wanted` affects rank only, never the filters, so this holds; the test in Step 5 pins it.
2. **The candidate cache stays context-free.** `_cache_key` (line 143) is `(skill, level, equipment, inventory, bank, skills)`. Folding `ctx` into it would multiply the cache by objective state and undo a fix that took a 47.0s producer down. Apply `wanted` *after* the cache read, building a new list — never mutating the cached one, which is returned by reference.

- [ ] **Step 1: Write the failing wiring tests**

Add to `tests/test_ai/test_skill_grind_target.py`. Match the fixtures already in that file for building a `WorldState` and `GameData`; do not invent new ones.

```python
def test_a_gear_target_rung_is_marked_wanted_and_a_plain_one_is_not():
    """`wanted` was constructed as the literal False at the sole production
    producer, so the key added on 2026-06-24 had never been able to fire. This
    is the wiring that lets it."""
    ctx = dataclasses.replace(NO_PROFILE_CONTEXT,
                              near_term_targets=frozenset({"copper_dagger"}))
    cands = build_selectable_grind_candidates(
        "weaponcrafting", _STATE, _GAME_DATA, ctx)
    by_code = {c.code: c for c in cands}
    assert by_code["copper_dagger"].wanted is True
    assert by_code["apprentice_gloves"].wanted is False


def test_a_siblings_supply_target_is_marked_wanted():
    """Objective 1 of the spec: a rung a sibling has published demand for is a
    keeper for the fleet even when this character does not want it."""
    ctx = dataclasses.replace(NO_PROFILE_CONTEXT,
                              supply_target=("copper_dagger", 1, 3))
    cands = build_selectable_grind_candidates(
        "weaponcrafting", _STATE, _GAME_DATA, ctx)
    by_code = {c.code: c for c in cands}
    assert by_code["copper_dagger"].wanted is True


def test_the_candidate_cache_is_not_keyed_by_context():
    """The cache key is (skill, level, equipment, inventory, bank, skills) and
    must stay that way: folding ctx in would multiply it by objective state and
    undo the fix that took this producer from 47.0s. `wanted` is applied AFTER
    the cache read, so the same state under two contexts must return the same
    codes with different `wanted` flags -- and the cached list must not be
    mutated by the first read.
    """
    ctx_a = dataclasses.replace(NO_PROFILE_CONTEXT,
                                near_term_targets=frozenset({"copper_dagger"}))
    ctx_b = NO_PROFILE_CONTEXT
    first = build_selectable_grind_candidates(
        "weaponcrafting", _STATE, _GAME_DATA, ctx_a)
    second = build_selectable_grind_candidates(
        "weaponcrafting", _STATE, _GAME_DATA, ctx_b)
    assert [c.code for c in first] == [c.code for c in second]
    assert any(c.wanted for c in first)
    assert not any(c.wanted for c in second)


def test_context_changes_the_rank_but_never_whether_a_grind_exists():
    """`LevelSkill.is_applicable` calls this with NO context and asks only
    `is not None`; `next_grind_goal` calls it WITH context. If a
    context-dependent term could empty the candidate set the two walks would
    disagree about whether a grind exists at all -- the
    selection-says-yes/emission-says-no split behind the wool livelock. `wanted`
    is a ranking term only, so existence is context-invariant.
    """
    ctx = dataclasses.replace(NO_PROFILE_CONTEXT,
                              near_term_targets=frozenset({"copper_dagger"}))
    with_ctx = skill_grind_target("weaponcrafting", _STATE, _GAME_DATA, ctx=ctx)
    without = skill_grind_target("weaponcrafting", _STATE, _GAME_DATA)
    assert (with_ctx is None) == (without is None)
```

Replace `_STATE` and `_GAME_DATA` with whatever the file's existing fixtures are named, and pick two real weaponcrafting codes from that fixture's catalog if `copper_dagger` / `apprentice_gloves` are not both in it. `dataclasses` and `NO_PROFILE_CONTEXT` must be imported at the top of the test file.

- [ ] **Step 2: Run them to verify they fail**

```bash
uv run pytest tests/test_ai/test_skill_grind_target.py -v -k "wanted or context or cache_is_not_keyed"
```

Expected: FAIL with `TypeError: build_selectable_grind_candidates() takes 3 positional arguments but 4 were given`.

- [ ] **Step 3: Add the `wanted` projection to the producer**

In `src/artifactsmmo_cli/ai/tiers/skill_grind_target.py`, add to the imports at the top:

```python
import dataclasses
```

and extend the existing `selection_context` import line to:

```python
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
```

Add this function immediately above `build_selectable_grind_candidates`:

```python
def _with_wanted(candidates: list[GrindCandidate],
                 ctx: SelectionContext) -> list[GrindCandidate]:
    """`candidates` with `wanted` set from `ctx`, as a NEW list.

    APPLIED AFTER THE CACHE, deliberately. `_cache_key` is a function of the
    STATE — skill, level, equipment, inventory, bank, skills — and nothing else.
    Folding the context in would multiply the cache by objective state and undo
    the hoist that took this producer from 47.0s of a 67.3s search. `wanted` is
    a projection of the context onto an already-computed list, so it costs one
    rebuild of ~10 dataclasses per call and leaves the memo intact.

    A NEW LIST, never a mutation: `build_selectable_grind_candidates` returns
    the cached list BY REFERENCE, so writing `wanted` into it would poison every
    later reader — including `LevelSkill.is_applicable`, which passes no context
    at all and must keep seeing `wanted=False`.

    Two sources, both already on the context. `near_term_targets` is the
    usable-now gear ∪ tool target set — crafting one of those gains the SAME
    skill xp and yields a keeper instead of a throwaway (2026-06-24: pure
    cheapest-chain greed made the bot craft a value-10 `apprentice_gloves`
    while ignoring the committed value-83 `copper_dagger`). `supply_target[0]`
    is the item code a SIBLING published demand for this cycle, so the fleet's
    need counts the same as this character's own.
    """
    supply = ctx.supply_target[0] if ctx.supply_target is not None else None
    return [dataclasses.replace(
        c, wanted=(c.code in ctx.near_term_targets or c.code == supply))
        for c in candidates]
```

- [ ] **Step 4: Thread `ctx` through both public functions**

Change the signature of `build_selectable_grind_candidates` to:

```python
def build_selectable_grind_candidates(skill: str, state: WorldState,
                                      game_data: GameData,
                                      ctx: SelectionContext = NO_PROFILE_CONTEXT
                                      ) -> list[GrindCandidate]:
```

Change its cache-hit branch (currently lines 235-237) to:

```python
    if hit is not None:
        cache.move_to_end(key)
        return _with_wanted(hit, ctx)
```

Change its `wanted=False` field (line 275, the one with the "No objective context in this standalone path" comment) to `wanted=False,` with this comment instead:

```python
            # The context-free default. `_with_wanted` overwrites this from the
            # caller's ctx below; the CACHED list keeps False so a later
            # context-free reader (LevelSkill.is_applicable) is unaffected.
            wanted=False,
```

Change the final two lines of the function to:

```python
    cache[key] = candidates
    if len(cache) > CACHE_MAX_ENTRIES:
        cache.popitem(last=False)
    return _with_wanted(candidates, ctx)
```

Change `skill_grind_target` to:

```python
def skill_grind_target(skill: str, state: WorldState, game_data: GameData,
                       reserved: frozenset[str] = frozenset(),
                       ctx: SelectionContext = NO_PROFILE_CONTEXT) -> str | None:
    candidates = [
        c for c in build_selectable_grind_candidates(skill, state, game_data, ctx)
        if not any(mat in reserved for mat in (game_data.crafting_recipe(c.code) or {}))
    ]
    chosen = skill_grind_selection_pure(skill, state.skills.get(skill, 0), candidates)
    return chosen or None
```

Note the existing call at line 265-267 already passes `NO_PROFILE_CONTEXT` to `acquisition_actions` — that is a *different* parameter (the acquisition profile) and must stay `NO_PROFILE_CONTEXT`. Do not replace it with the new `ctx`: `acquisition_actions` reading an objective profile would change the cached `acquire_steps` and put objective state back into the memo through the side door.

- [ ] **Step 5: Run the wiring tests**

```bash
uv run pytest tests/test_ai/test_skill_grind_target.py -v
```

Expected: all pass, including the four new ones and the pre-existing `test_a_HELD_rung_is_not_free_because_the_grind_must_CRAFT_another`.

- [ ] **Step 6: Pass the context at the one call site that has one**

In `src/artifactsmmo_cli/ai/level_skill_expand.py`, change lines 82-83 from

```python
    rung = (skill_grind_target(skill, state, game_data, frozenset(ctx.step_profile))
            or skill_grind_target(skill, state, game_data))
```

to

```python
    rung = (skill_grind_target(skill, state, game_data,
                               frozenset(ctx.step_profile), ctx)
            or skill_grind_target(skill, state, game_data, ctx=ctx))
```

Both arms take the ctx: the reserved-preference arm and the unreserved fallback rank the same way, so falling back never silently changes the ranking basis as well as the reservation.

- [ ] **Step 7: Run the expansion tests**

```bash
uv run pytest tests/test_ai/test_level_skill_expand.py tests/test_ai/test_level_skill.py -q 2>&1 | tail -5
```

Expected: pass.

- [ ] **Step 8: Run ruff and mypy on the changed files**

```bash
uv run ruff check src/artifactsmmo_cli/ai/tiers/skill_grind_target.py \
                  src/artifactsmmo_cli/ai/level_skill_expand.py \
                  src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py
uv run mypy src/artifactsmmo_cli/ai/tiers/skill_grind_target.py \
            src/artifactsmmo_cli/ai/level_skill_expand.py
```

Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/skill_grind_target.py \
        src/artifactsmmo_cli/ai/level_skill_expand.py \
        tests/test_ai/test_skill_grind_target.py
git commit -m "fix(ai): the grind's \`wanted\` key was dead — the sole producer passed False

GrindCandidate is constructed in exactly one place in src/, and it passed the
literal wanted=False, so the key added on 2026-06-24 to stop the bot crafting a
throwaway instead of the committed weapon has never been able to fire in
production. The live symptom is the same item, apprentice_gloves, for the same
reason.

wanted now comes from the SelectionContext the caller already holds:
near_term_targets (this character's usable-now gear and tool targets) and
supply_target[0] (an item a sibling published demand for this cycle).

Applied AFTER the candidate cache, as a new list rather than a mutation: the
cache key stays a function of state alone -- folding ctx in would multiply it by
objective state and undo the hoist that took this producer from 47.0s -- and the
cached list is returned by reference, so a context-free reader keeps seeing
False. Ranking only, never membership, so LevelSkill.is_applicable (no ctx) and
next_grind_goal (ctx) still agree on whether a grind exists."
```

---

### Task 4: Measure whether XP is actually proportional to `craft_level`

**Files:**
- Create: `formal/diff/craft_xp_replay.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (it measures the game, not the code).
- Produces: a measurement, and either a confirmation or a refutation of the numerator assumption in `_beats`.

**Background.** The rate's numerator is `craft_level`, and the spec names the assumption behind it as **unverified**: the server pays `Round((XP_base + (content_level / skill_level) * k) * level_penalty * wisdom_bonus)`, neither `XP_base` nor `k` is published or in the API, and `level_penalty` varies across rungs by an unmeasured factor. At fixed skill level XP is monotone nondecreasing in content level — enough for an *ordinal* proxy, not for the *cardinal* numerator of a ratio.

This is exactly the shape of claim that has cost this project the most, and the repo has a precedent for settling it: `formal/diff/gather_xp_replay.py` established the grey band from 760 live gathers rather than from the doc's loose prose ("THE BOUNDARY IS OBSERVED, NOT ASSUMED"). Read that file first — this task is its sibling for crafts.

The data: committed play-traces, whose `Cycle` rows carry `delta_skill_xp_json` (see `ai/learning/models.py:62` and the parser `ai/learning/projections.py:103`).

**A null result is a result.** If the traces contain too few distinct `(craft_level, skill_level)` pairs to say anything, the deliverable is the measured statement that they do, with the counts. Do not manufacture a conclusion, and do not change `_beats` on thin evidence.

- [ ] **Step 1: Read the precedent**

```bash
sed -n 1,80p formal/diff/gather_xp_replay.py
```

Note how it structures the replay, where it finds the trace files, and how it reports the boundary table. Follow that structure.

- [ ] **Step 2: Write the replay**

Create `formal/diff/craft_xp_replay.py`. It must:

1. Walk the committed play-traces, selecting cycles whose action was a craft.
2. For each, record `(item_code, craft_level, skill_level_at_the_time, observed_skill_xp)` from `delta_skill_xp_json`.
3. Group by `skill_level`, and within each group report observed XP against `craft_level`.
4. Print a table of `(skill_level, craft_level) -> n, mean xp, min, max`.
5. Report, per skill level with at least two distinct craft levels, the ratio `xp / craft_level` and whether it is constant within the observation noise.

Give it a module docstring stating what question it answers, in the style of `gather_xp_replay.py`.

- [ ] **Step 3: Run it and record the output**

```bash
uv run python formal/diff/craft_xp_replay.py > /tmp/craft_xp.txt 2>&1; echo "rc=$?"; cat /tmp/craft_xp.txt
```

Paste the full table into your report.

- [ ] **Step 4: Record the verdict in `_beats`**

Whatever the answer, replace the sentence in `_beats`' docstring that reads "The assumption is named here rather than hidden: see `formal/diff/craft_xp_replay.py` for what the play-traces say about it." with the measured statement. One of:

- *supported:* `Measured over N crafts in the committed play-traces (formal/diff/craft_xp_replay.py): xp / craft_level is constant to within ±X at fixed skill level, across craft levels A..B. The proportionality holds on the observed range.`
- *refuted:* `Measured over N crafts (formal/diff/craft_xp_replay.py): xp / craft_level is NOT constant — <the shape found>. craft_level therefore ORDERS rungs correctly but misprices the ratio, and the numerator wants replacing with <what the data supports>. Not done here; recorded as a residual.`
- *inconclusive:* `The committed play-traces contain only N crafts across M distinct (craft_level, skill_level) pairs (formal/diff/craft_xp_replay.py), too few to test proportionality. The assumption stands UNVERIFIED, not confirmed.`

Fill in the real numbers. Do not use a template phrase with a placeholder left in it.

- [ ] **Step 5: Commit**

```bash
git add formal/diff/craft_xp_replay.py src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py
git commit -m "test(grind): measure whether craft xp is proportional to craft_level

The rate's numerator is craft_level, which the published formula justifies only
as an ORDINAL proxy -- XP_base, k and the per-rung level_penalty are all absent
from the API. Using it as the CARDINAL numerator of a ratio is a further
assumption, and this replays the committed play-traces to test it, the way
gather_xp_replay.py settled the grey band from 760 live gathers instead of from
the doc's prose.

The measured verdict is now in _beats' docstring in place of the assumption."
```

---

### Task 5: Live acceptance and the full gate

**Files:**
- Modify: `docs/superpowers/specs/2026-08-14-grind-rung-xp-rate-ranking-design.md` (residuals, if the live run finds any)

**Interfaces:**
- Consumes: everything from Tasks 1-4.
- Produces: the evidence that the change fires in production, and a green gate.

**Background.** Green tests are not enough here. Earlier in this investigation a fixture disagreed with live state and nearly produced the wrong conclusion, and this project has a standing rule that planner/cost/goal changes must be shown firing on a live character before they are called done. The gate has not run since commit `ec613f0d`.

- [ ] **Step 1: Confirm the bot is not running**

```bash
pgrep -af "artifactsmmo" || echo "nothing running"
```

The gate and the mutation runner must not run concurrently with anything importing `src/`. If the bot is up, stop here and report — do not kill the user's process yourself.

- [ ] **Step 2: Probe the live selection for Lor and HAL**

```bash
uv run artifactsmmo plan Lor 2>&1 | tail -40
uv run artifactsmmo plan HAL 2>&1 | tail -40
```

Expected: neither character's weaponcrafting grind selects `apprentice_gloves`. Lor should select `sticky_dagger` or `fire_staff`; HAL should select `water_bow`. **Report what actually happened, including if it disagrees with this expectation** — the ratios in the spec are from a design-time probe against state that has since moved, so a different-but-higher-rate rung is a pass and the same old gloves is a failure.

If the CLI subcommand differs, find the right one — `reference_cli_query_game_api` records that `uv run artifactsmmo` queries the live API — and record the command you used.

- [ ] **Step 3: Run the full gate**

```bash
bash formal/gate.sh > /tmp/gate.txt 2>&1; echo "rc=$?"
tail -40 /tmp/gate.txt
```

Never pipe this into `tail` directly — the exit code would be `tail`'s, and a visible `GATE FAIL` has been read as `rc=0` in this repo before.

Expected: `rc=0`, 0 errors, 0 warnings, 0 skipped, 100% coverage, 0 PLANNER_BUG.

- [ ] **Step 4: Record what the live run showed**

Append to the spec's Residuals section a bullet stating what the live probe actually selected for each character, with the rung codes and the date. If the gather-arm or any case could not be reached live, say so explicitly rather than omitting it — the predecessor branch's honest limit ("runtime activation did NOT fire spontaneously") is the model.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-08-14-grind-rung-xp-rate-ranking-design.md
git commit -m "docs(spec): record what the live grind actually selected after the rate change"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| The ranking (4-key order, cross-multiplication) | 1 |
| `wanted` as marginal-cost credit (Option A) | 1 |
| Two tie-breaks under the credit | 1 |
| Finding 3 — the suite cannot see this change | 1 (Steps 1, 2, 5, 6) |
| Filters unchanged, all four | 1 (Step 4 forbids editing them), 2 (filter theorems untouched) |
| `beats_prefers_cheaper_chain` falsified and replaced by three theorems | 2 |
| Non-vacuity of new witnesses | 2 (Global Constraints + theorem hypotheses use distinct nonzero values) |
| Differential re-derived with a discriminating case | 2 (Steps 7-8) |
| Mutation anchors refreshed in the same commit | 2 (Steps 4-6) |
| Reviving `wanted` — ctx threading | 3 |
| Membership must not move | 3 (Step 1's fourth test, Step 6) |
| Cache stays context-free | 3 (Step 1's third test, Step 3's docstring) |
| Sibling demand via `supply_target` | 3 (Step 1's second test, Step 3) |
| `craft_level` proxy — bounded replay task | 4 |
| Live acceptance, not fixture-only | 5 (Step 2) |
| Gate serialized, not piped to `tail` | 5 (Steps 1, 3) |

No spec requirement is without a task.

**Type consistency:** `GrindCandidate`'s seven fields are unchanged throughout. `build_selectable_grind_candidates` gains `ctx: SelectionContext = NO_PROFILE_CONTEXT` as its fourth parameter in Task 3 and is called with it positionally from `skill_grind_target` only. `skill_grind_target` gains `ctx` as its *fifth* parameter, after `reserved`, so the two existing positional call sites (`ai/actions/level_skill.py:68`, `ai/level_skill_expand.py:83`) keep working; `level_skill_expand`'s second arm passes it by keyword (`ctx=ctx`) because it skips `reserved`. `_with_wanted` takes and returns `list[GrindCandidate]`.

**Known risk, named rather than hidden:** Task 1 Step 8 depends on `scripts/extract_lean.py` handling local `let` bindings and a conditional expression inside `_beats`. Both constructs are already present in the generated output for this very module (`skill_grind_selection_pure` emits three `let`s), and `ast.Mult` and `ast.IfExp` are both handled by the extractor — but `_beats`' `if best is None: return True` compiles to a Lean `match`, and the bindings must land inside its `some` branch. If the extractor errors or emits something that will not typecheck, that is a finding to report, not a reason to restructure `_beats` quietly.
