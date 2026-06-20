# PLAN — Progress-Gated Sticky Release (kill the zombie commitment, discharge `hquiet`)

Status: **Phase 1 in progress** (2026-06-20). Multi-session.

## The bug (trace-confirmed, play-trace-Robby.jsonl, 1982 cycles)

`chosen_root` = `ReachSkillLevel(weaponcrafting, 5)` for **1028 consecutive cycles**
— one unbroken run, never released. During it:
- weaponcrafting xp **frozen at 75** (mining climbed 598→2095).
- 0 weapon crafts. Action was `Gather(copper_rocks)` ×815, `Craft(copper_bar)` ×78.
- the committed skill-grind goal (`GatherMaterials(copper_dagger, held+1)`) was the
  selected goal in only **7** cycles of the entire file, **0** during the commit —
  it loses arbitration to collect/guard means every cycle.

### Root cause — the 2026-06-19 zombie-release checks the wrong signal

1. **Tier-2 root sticky** (`tiers/strategy.py:586-595`): `STICKY_DOMINANCE_RATIO = 3/2`.
   sticky (skill 2.04) is kept whenever `top_final ≤ 3/2 · sticky_final`
   (gear 2.5 ≤ 3/2·2.04 = 3.06 → TRUE). The higher gear root cannot dislodge it.
2. **Release** (`player.py:340`): feeds `last_chosen_root := repr(chosen_root)` only
   when `chosen_step_alive`. That flag = "did the committed step produce a *goal
   object*?" (`strategy_driver.py:827`, `step_goal is not None`).
3. **The flag is permanently True**: `objective_step_goal(ReachSkillLevel(weaponcrafting))`
   → `build_grind_candidates('weaponcrafting')` always finds `copper_dagger`
   (obtainable, in-skill) → returns a non-None `GatherMaterials` goal → anchor
   re-commits forever, EVEN THOUGH that goal never wins arbitration and the skill
   never levels.

The predicate measures **goal production, not goal execution / progress.** A
non-None goal that loses every arbitration and never moves the measure is an
**alive-but-inert zombie** the 2026-06-19 fix cannot see.

## The fix (decisions locked with the user 2026-06-20)

**A. Release trigger = progress-gated (measure descent).** Keep the sticky anchor on
a committed root only when that root's **own reach-50 sub-measure has strictly
descended since commit**. A frozen root (skill xp flat) never descends its
sub-measure → released. A genuinely-progressing gear root (accumulating a material,
crafting an intermediate) does descend its sub-measure → kept. This subsumes the
weaponcrafting zombie AND the "gather-copper-forever-never-craft" gear zombie,
and is **K-free** (no magic patience counter).

**B. Proof scope = discharge `hquiet` → unconditional reach-50.** The progress-gate
is exactly the missing fact behind `LevelingDescent.fightsBelowCap_of_grounded`'s
named residual `hquiet` (LevelingDescent.lean:154). `hquiet`'s explicit gap is the
case where `objectiveStep` fires but is **not** a fight (`objectiveStepIsFight =
false`) — i.e. a zombie commitment to a gather/grind. Prove: no root remains
chosen below 50 without descending the measure ⇒ the arbiter always re-selects a
fight-bearing root ⇒ `hquiet` holds ⇒ `ai_reaches_fifty_grounded` becomes
unconditional modulo only `hspawn` (runtime `1 ≤ level`) and LIV-001.

**C. Weights = re-derived from the progress guarantee.** Not assumed. See "Weight
derivation" below.

## Weight derivation (the "correct weights" deliverable)

Claim: **with the progress-gate, the zombie property is weight-INDEPENDENT, and
the legitimate weight constraints are exactly the bootstrap-ordering ones.**

- The weaponcrafting zombie arose NOT because skill out-scored gear (it did not:
  2.04 < 2.25 < 2.5) but because the bad sticky feedback pinned a non-progressing
  root. Once the anchor is fed back **only for progressing roots**, a sticky root
  that holds is — by the gate — descending the measure, so it *cannot* zombie for
  ANY `STICKY_DOMINANCE_RATIO ≥ 1`.
- Therefore `STICKY_DOMINANCE_RATIO = 3/2` is **provably liveness-safe** (it is a
  flap-vs-responsiveness knob, not a liveness parameter). Theorem role:
  `sticky_progress_safe` — a sticky-held root strictly descends the measure,
  ∀ ratio ≥ 1.
- The **score ordering** gear > char_level > skill (2.5 > 2.25 > 2.04) is the
  bootstrap-correctness constraint: when the top-scored progress-capable root is
  chosen, the bot pursues gear-then-level-then-skill. Constraint to prove:
  among progress-capable (plannable + measure-descending) roots, the chosen one
  is the max-scored, and below 50 a max-scored progress-capable root is
  fight-bearing or fight-enabling (descends levelDeficit/xpDeficit). Theorem role:
  `chosen_is_max_progressing` + `progressing_below_fifty_is_fight_bearing`.

Net "correct weights": **ratio ≥ 1 (keep 3/2); category ordering gear > char >
skill preserved.** The fix is the release gate, not a weight change — and we PROVE
the weights were never the liveness lever.

## Components to add to `formal/`

| Component | Lean module | Roles |
|---|---|---|
| Tier-2 sticky select | `Formal/StickySelect.lean` | `validity` (matches decide()), `sticky_kept_iff` (ratio gate), `release_of_no_progress` |
| Progress gate | `Formal/StickySelect.lean` | `sticky_progress_safe` (held ⇒ descends ∀ratio≥1), `no_zombie` (bounded run length) |
| Weight ordering | `Formal/StickySelect.lean` | `chosen_is_max_progressing`, `progressing_below_fifty_is_fight_bearing` |
| `hquiet` discharge | `Formal/Liveness/LevelingDescent.lean` (extend) | `hquiet_of_no_zombie`, upgrade `ai_reaches_fifty_grounded` to drop `hquiet` |

Gate wiring:
- pure-core decision theorems → `Manifest.lean` (#check) + `Contracts.lean` (exact-statement pins).
- liveness capstone → `LivenessAudit.lean` (#print axioms).
- differential: extend `diff/` — a NEW `test_sticky_select_diff.py` binding Lean
  `stickySelect` to the production `decide()` sticky override (currently UNbound —
  `test_decide_key_diff.py` covers the sort but not the sticky logic).
- mutation: the new pure core must have mutants killed by the differential.

## Implementation (Phase 2)

- Extract `src/artifactsmmo_cli/ai/tiers/sticky_select_core.py` — pure function
  `sticky_select_pure(candidates, last_chosen_root, ratio, progressed: bool) ->
  (chosen_root, chosen_step)` mirroring the Lean def. `progressed` is the
  sub-measure-descended signal computed by the impure layer.
- Impure layer (`player.py`): compute `progressed` = committed root's sub-measure
  strictly below its commit baseline; feed `last_chosen_root` only when progressed.
  Replaces the `chosen_step_alive` gate.
- Sub-measure per root: skill→skill_xp[S] delta; char→level/xp delta; gear→
  obtainment-deficit delta (materials-on-hand + craft-steps-remaining). Track
  baseline in player state at commit.

## Phase order / checkpoints

1. ✅ Root cause (trace) — DONE.
2. ✅ **Phase 1**: Lean `Formal/Liveness/StickySelect.lean` — DONE 2026-06-20.
   - `stickyChoose` (faithful to strategy.py:582-595 post-sort) + `nextLast` (the
     progress-gated release replacing `chosen_step_alive`).
   - `sticky_requires_progress` (no-zombie core), `sticky_progress_safe`
     (ratio-independence — the "correct weight" result), `released_picks_top`,
     `stickyChoose_mem`, `kept_when_progressing` + `dropped_when_frozen` (non-vacuity).
   - Kernel-green; `#print axioms` = {propext, Classical.choice, Quot.sound} on ALL.
   - Gate-wired: 5 `#check` in Manifest.lean, 3 exact-statement pins in Contracts.lean.
     Both modules rebuild clean.
3. ◑ Phase 1b: no-zombie liveness lemma PROVEN 2026-06-20 — but NOT the full hquiet
   discharge (honest scope below).
   - `StickySelect.no_infinite_sticky_hold` — abstract: a sticky-held non-top root at
     EVERY cycle, with a progress signal faithfully witnessing strict WF-measure
     descent, is contradictory. Standard axioms only.
   - `Formal/Liveness/ZombieFreedom.no_infinite_zombie_below_fifty` — concrete instance
     at the REAL reach-50 lex measure (`measureLt` / `measureLt_wellFounded`). Inherits
     ONLY the pre-existing measure axiom LIV-001 (`Measure.xpToNextLevel`); NO new axioms.
   - Gate-wired: Manifest `#check` (×2), Contracts exact-statement pin (no_infinite_sticky_hold),
     LivenessAudit `#print axioms` block. All three modules rebuild clean.

   **HONEST SCOPE — what this does NOT yet do (do not over-claim):**
   - It does NOT modify `LevelingDescent.ai_reaches_fifty_grounded`; that capstone
     still carries `hquiet` + `hspawn` + LIV-001 as named residuals.
   - The literal Lean `hquiet` Prop is about ladder-PREFIX blocker-quieting (the
     `Blocker*` program's concern), which this work does not touch.
   - What this work DOES address is the SEPARATE `objectiveStepIsFight` arming-
     FAITHFULNESS caveat (Measure.lean:169 / PerceptionRefresh.lean:119-122): the model
     sets the arming optimistically-true, with a documented gap. The gap had TWO
     components — the named items-task-defer case AND an unrecognized ZOMBIE case
     (objectiveStep resolves to a gather/grind, not a fight). This work PROVES the
     progress-gate eliminates the zombie component (modulo the differential
     `hprogFaithful`), shrinking the arming gap to items-task-defer only.
   - Remaining for true unconditional reach-50: replace `perceptionRefresh`'s
     unconditional `objectiveStepIsFight := true` with a value DERIVED from the
     progress-gated objective selection, threading through FightFairness / BlockerSettled
     / the capstone proof term so `no_infinite_zombie_below_fifty` is actually CONSUMED.
     Plus the `hprogFaithful` differential discharge (Phase 3). This is multi-session.

3b. ◑ Phase 1b-cont: `Formal/Liveness/GatedArming.lean` — DONE 2026-06-20 (the BRIDGE,
    not the splice). DERIVES the arming as `gatedArming cands lastChosen ratio
    fightBearing := fightBearing (stickyChoose …)`, replacing the fiat at the
    definitional level. Proven: `gatedArming_eq_top_of_released` (released ⇒ arming =
    top root's fight status), `gatedArming_true_of_fight`,
    `arming_false_of_held_nonfight` (held non-fight ⇒ suppressed — load-bearing link),
    and the headline `no_infinite_zombie_suppression` — **CONSUMES**
    `StickySelect.no_infinite_sticky_hold` to prove a non-fight root cannot suppress the
    arming forever. Standard axioms only. Gate-wired: Manifest #check (×3), LivenessAudit
    #print axioms (×3).

    **HONEST: this is the bridge the capstone WILL consume, NOT the splice itself.**
    `perceptionRefresh` / `ai_reaches_fifty_grounded` are UNCHANGED — they still use the
    fiat `:= true`. The actual splice is blocked on TWO larger items, both confirmed
    this session:
    (i) the cycle dynamics (`cycleStep`/`applyActionKind`/all 23 means' `planFor`) must
        thread the selection state so the derived arming reads a live selection, not
        inert State defaults;
    (ii) the descent argument must move from "fights every below-50 cycle"
        (`FightsBelowCap`) to "DESCENDS THE MEASURE every below-50 cycle" — healthy gear
        bootstrap GATHERS (descending the skill-xp slot) without fighting, so the
        fight-every-cycle invariant is fundamentally too strong. This is the documented
        out-of-scope `ProgressAction` fuel-bounding work (`LevelingDescent.lean:29-33`).
4. ✅ Phase 2: Python SHIPPED 2026-06-20. `sticky_select_core.py` (`sticky_choose` /
   `next_last`, mirror Lean) + `root_progress.py` (`root_progress_value`, the
   `hprogFaithful` production witness, keyed to root TYPE). `decide()` routes through
   `sticky_choose`; `player._update_sticky_anchor` replaces the `chosen_step_alive`-only
   gate with the progress-gated `next_last` (frozen committed-axis ⇒ zombie released).
   Full suite **3613 passed, 100% coverage**, mypy clean. The 1028-cycle weaponcrafting
   zombie is released in production. Tests: `test_sticky_select_core.py`,
   `test_player_sticky_anchor.py`.
5. ☐ Phase 3: differential `test_sticky_select_diff.py` (bind `sticky_choose`↔Lean
   oracle) + mutation + run `gate.sh` (serialized). Manifest/Contracts/Audit pins for the
   Lean side already in. ← NEXT for full gate lockstep.
6. ☐ Phase 4: adversarial proof review (is `root_progress_value` faithful to measure
   descent? is `no_infinite_sticky_hold` non-vacuous? — it is: held+progress is realizable).
7. ✅ Phase 5: unit suite at 100% coverage (project bar) — green with the new modules.

## Honesty risks to watch (Phase 4)
- `no_zombie` must be NON-VACUOUS: exhibit a satisfying run where a root IS held
  (progressing) and one where it IS released (frozen). Avoid `False → P`.
- The sub-measure faithfulness (Lean model ↔ production `progressed` bool) is the
  trust boundary — must be differentially bound, not asserted.
- `hquiet_of_no_zombie` must not smuggle the conclusion through an optimistic
  `objectiveStepIsFight` set value. The discharge has to come from the release
  gate forcing fight-bearing selection, differentially grounded.
