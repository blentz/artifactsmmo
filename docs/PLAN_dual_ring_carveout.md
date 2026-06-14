# PLAN: Narrow the one-slot-per-code invariant for rings (formal-development)

> Formal-development task. Implements **components 5–7** of
> `docs/superpowers/specs/2026-06-14-per-slot-gear-roots-dual-ring-design.md`
> (Addendum 2026-06-14). Branch: `feat/per-slot-gear` (worktree
> `/home/blentz/git/artifactsmmo-perslot`).

**Goal:** Relax the kernel-proved ONE-SLOT-PER-CODE loadout invariant so that
**ring-type** codes may occupy both ring slots (live probe 2026-06-14: server
returns HTTP 200 for a duplicate `copper_ring`), while every other code keeps
the rule — in lockstep across the Lean model, the extracted Python core, and
the differential/mutation gate, with no proof weakened beyond the rings carve-out.

## The non-obvious correctness constraint (drives the whole model)

`forbiddenIn` today serves **two** purposes at once:
1. the server's one-slot-per-code rule (HTTP 485), and
2. an implicit **ownership cap** — by forbidding a code from any 2nd slot, the
   algorithm can never wear more copies of a code than the 1 it implicitly
   assumes, so the output is always realizable
   (`equipment/realizable_loadout.is_realizable`).

Simply exempting rings from the filter breaks (2): with a single owned
`copper_ring` the algorithm would assign it to BOTH ring slots → an
**unrealizable** loadout (`ownership=1 < demand=2`), which the
`OptimizeLoadoutAction.apply` assertion would then fire on. The probe only
succeeded because Robby owned **two** rings.

**Correct generalized rule.** A code `c` is forbidden for a further slot iff the
number of slots already holding `c` in the projected result has reached its
per-code cap:

```
cap(c) = ownership(c)               if dupAllowed(c)     -- rings: as many as you own
       = 1                          otherwise            -- everyone else: server 485 rule
forbidden(c, result, slot) = (count of c in result at OTHER slots) >= cap(c)
```

For non-ring codes `cap=1` reproduces today's `_in_result_elsewhere` exactly
(no behavioural change). For rings it permits a 2nd slot **only when a 2nd copy
is owned**, preserving realizability.

`dupAllowed(c)` ≡ `game_data.item_type(c) in _DUPLICATE_SLOT_TYPES`
(`_DUPLICATE_SLOT_TYPES = {"ring"}`, matching the objective layer's
`_DUPLICATE_FILL_TYPES`). In the Lean model it is abstracted as an input
predicate `dupAllowed : Code → Bool` (per lean-modeling: dependencies are inputs).

`is_realizable`/`ownership` (`realizable_loadout.py`) are ALREADY
ownership-counted and need **no change** — they already accept a code in N slots
iff owned N times. The entire carve-out lives in the `pick_loadout` feasibility
filter and its Lean mirror.

## Component map (file → change → theorem roles)

### C5a — Lean model: ownership-capped feasibility (`formal/Formal/RealizableLoadout.lean`)
- **`forbiddenIn`** (`:354`): add `dupAllowed : Code → Bool` and an `ownership`
  count; replace the `.any (= some code)` membership test with the cap test
  above. Keep it a pure computable `Bool` def (must run in the oracle).
- **`feasibleCands`** (`:361`): thread `dupAllowed` into the `forbiddenIn` call.
- **`pickLoadout` / `pickLoadoutAux`**: thread `dupAllowed` as a parameter.
- **`dupFreeExcept`** (new, beside `dupFree` `:613`):
  `def dupFreeExcept (dupAllowed) (sl) : Prop := ∀ c, dupAllowed c = false → slotCount c sl ≤ 1`.
  `dupFree` is retained (used elsewhere) but the headline contract weakens to
  `dupFreeExcept` — **the only intended weakening**.

### C5b — Lean theorems (the contracts)
| Theorem (role) | Change |
|---|---|
| `pickLoadout_one_slot_per_code` (**safety-invariant**) | restate: input `dupFreeExcept dupAllowed (currents)` → output `dupFreeExcept dupAllowed (pickLoadout …)`. Non-ring codes still ≤1; rings unconstrained by THIS theorem. |
| `pickLoadout_realizable` (**safety-invariant**, if present) | must still hold ∀ — the ownership-cap is what keeps it true for rings. If absent, **ADD** it: `is_realizable (pickLoadout …) inv equip = true`. This is the theorem that gives the ownership-cap its teeth. |
| `pickLoadout_485_copper_ring_regression` (**non-vacuity**) | **FLIP + RENAME** → `pickLoadout_dual_ring_fills_when_two_owned`: ownership `copper_ring ↦ 2`, dupAllowed ring → result `[some copper_ring, some copper_ring]`. ALSO add `pickLoadout_single_ring_no_dup_fill`: ownership `↦ 1` → ring2 stays `none` (realizability boundary). |
| `pickLoadout_ring_pair_regression` (**non-vacuity**) | recompute under the new rule (A,B both dupAllowed, ownership 1 each) and restate to the actual output; assert realizability holds. |
| `pickSlotStep_no_downgrade` (**monotonicity**) | re-verify: the no-downgrade argument must not rely on the old "no peer can hold a current code" fact for ring codes. Restate/guard if needed; do NOT silently weaken. |
| non-ring regressions (`pickLoadout_zero_score_no_fill`, etc.) | pass `dupAllowed = fun _ => false`; statements unchanged (proves backward-compat). |

### C5c — Manifest + Contracts (anti-weakening pins)
- `formal/Formal/Manifest.lean` (`:417`): update the renamed theorem; add the new
  realizability + single-ring-no-fill roles.
- `formal/Formal/Contracts.lean` (`:1931`): re-pin each role's EXACT new statement
  via `example : <full statement> := @thm`. The weakened-to-`dupFreeExcept`
  statement is pinned so it cannot silently weaken further.

### C5d — Python core (`src/artifactsmmo_cli/ai/equipment/scoring.py`)
- `pick_loadout` (`:211`): replace `_in_result_elsewhere(code, slot)` with the
  ownership-capped `_forbidden(code, slot)` using
  `dupAllowed = game_data.item_type(code) in _DUPLICATE_SLOT_TYPES` and
  `ownership(code, …)`. Regenerate the sha header tying it to the Lean def.
  Update the docstring (the current one explicitly states the spare-ring case is
  illegal — that is now false for rings).
- `_DUPLICATE_SLOT_TYPES = frozenset({"ring"})` module constant.

### C5e — other impl enforcement sites
- `actions/equip.py` (`:65`): the `is_applicable` one-slot-per-code guard →
  exempt `dupAllowed` types (needs item type from game_data/state).
- `actions/optimize_loadout.py` (`:78`): the apply-time assertion already checks
  realizability via the `cur >= 1` decrement — verify it tolerates a ring in two
  slots when owned twice (it should, being ownership-counted); add a test.

### C6 — Differential + mutation gate (`formal/diff/`, `formal/gate.sh`)
- `diff/test_realizable_loadout_diff.py` (`:68` ring regression): the Hypothesis
  generator must now also emit **dup-allowed (ring) codes with ≥2 ownership** and
  assert oracle≡`pick_loadout` on dual-ring fills (today it likely only exercises
  the single-copy/no-dup path). Add the `dupAllowed` input to the oracle JSON
  contract + `Oracle.lean`.
- Re-run `mutate.py`: the ownership-cap branch and the `dupAllowed` branch each
  need a mutation-killing differential case (flip cap, drop dupAllowed → a mutant
  that always/never allows dup must die). Refresh stale mutation anchors
  (memory: run mutate.py after ai/ refactors).

### C7 — Honest integration test (replaces the assertion-light one)
- Replace `test_arbiter_equips_second_ring_into_empty_slot` (asserts only that the
  ring2 root is *chosen*) with one that:
  - state: `copper_ring` in `ring1_slot`, a spare `copper_ring` in inventory, item
    type ring → `EquipAction("copper_ring", "ring2_slot").is_applicable(state)` is
    **True**, and executing leaves `ring2_slot == "copper_ring"`;
  - **must FAIL on current `main`/branch (guard rejects) and PASS after C5e.**
- Add the single-owned-ring boundary unit test (no dup fill when only one owned).

## Phase order (formal-development workflow; gate green between phases)

1. **Phase 1 (prove):** C5a–C5c in the Lean model. Drive with `lean4:formalize` /
   `lean4:prove`; repair with the `lean4:proof-repair` agent; golf with
   `lean4:proof-golfer`. Gate parts 1–5 green (build, no-sorry, axiom-lint,
   manifest, contracts). **Axiom budget unchanged** — no new axioms; this is a
   core-only safety relaxation (memory: liveness-axiom-split — safety stays
   core-only, no Mathlib).
2. **Phase 2 (implement):** C5d–C5e to mirror the proved def exactly.
3. **Phase 3 (gate):** C6 — differential proves core≡code on dual-ring inputs;
   mutation gives the new branches teeth. Run `formal/gate.sh` **serialized**
   (memory: never concurrent with anything importing src, incl. the bot;
   `git diff src` after).
4. **Phase 4 (adversarial review):** read every changed/flipped theorem against
   reachable states — is the flipped regression telling the truth (server 200,
   2 owned) or a flattering lie? Confirm `dupFreeExcept` did not over-weaken
   (non-ring codes MUST still be pinned ≤1). Use `lean4:review` +
   `cavecrew-reviewer`. (memory: proofs-tell-false-stories — mandatory.)
5. **Phase 5 (unit suite):** C7 + ripple; `uv run pytest` 0/0/0/100%.

## Soundness / honesty checklist (Phase 4 gate)
- [ ] The ONLY weakening is `dupFree → dupFreeExcept`, and only for codes with
      `dupAllowed = true`. Non-ring codes remain provably ≤1 (pinned in Contracts).
- [ ] Realizability (`is_realizable (pickLoadout …)`) holds **unconditionally** —
      the ownership-cap, not the old filter, now carries it.
- [ ] The flipped regression matches the live probe (ring2 fills **iff** a 2nd
      copy is owned), and a single-owned-ring case proves it does NOT over-fill.
- [ ] Differential feeds dup-allowed codes with ownership ∈ {1, 2, 3}; mutation
      kills the cap and the dupAllowed branches.
- [ ] `git diff src` after every gate run is clean of poisoned predicates.

## Out of scope
- utility/artifact duplication (kept one-slot; no server evidence).
- any ranking / equip_value change.
- the per-slot-root groundwork (C1–C4, already committed on this branch).
