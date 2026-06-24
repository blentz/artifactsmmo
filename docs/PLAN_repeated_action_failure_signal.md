# PLAN: REPEATED_ACTION_FAILURE stuck signal

**Goal:** Add a 4th `StuckDetector` signal that fires when the SAME action_name
fails ≥ K times within a window of W recent cycles, *regardless of interspersed
progress* — the class of livelock the 478 bank loop (4550 cycles of
`Withdraw(ash_plank)→HTTP 478`) evaded because state varied, goals didn't
oscillate, and it wasn't 4 consecutive `<no_plan>`s.

**Thresholds:** `REPEATED_ACTION_WINDOW = 20`, `REPEATED_ACTION_FAILURE_THRESHOLD
= 10`. In 20 cycles, one specific action failing 10× (50% of the window) is a
livelock; conservative against transient retries. Handler suppresses the goal(s)
driving the repeatedly-failing action(s) — recoverable (L1=10cyc, L2=30cyc,
L3=StuckExit), like GOAL_OSCILLATION.

**Precedence:** appended LAST — frozen > osc > noprog > repeated > none. The
existing three stay higher-priority (more specific responses); repeated is the
backstop none of them catch. `noPlan` records are EXCLUDED from the count
(NO_PROGRESS owns the no-plan flood); only named-action failures count.

## Formal lockstep (recovery.py is gated by StuckDetector.lean)

- **StuckDetector.lean** — extend `Rec` with `action : Nat`; `Detector` with
  `ackRepeated`; `Signal.repeated`. New defs `actionFailCount`,
  `maxActionFailCount`, `checkRepeatedAction`. Theorem roles:
  - `repeated_threshold` — fires ↔ maxActionFailCount window ≥ threshold (defn).
  - `repeated_requires_failures` — max < threshold ⇒ never fires (safety).
  - `repeated_fire_witness` — fires ⇒ ∃ action code with ≥ threshold failing,
    non-noPlan records in the window (NON-VACUITY teeth).
  - `detect_repeated_last` — frozen/osc/noprog false ∧ repeated ⇒ detect=repeated.
  - `ack_suppression_repeated` / `ack_repeated_cannot_fire` — ack empties window.
  - UPDATE `detect_precedence` final clause: all FOUR false ⇒ none + repeated row.
  - trace regressions: 10-of-one-action-among-progress fires; 9 does not.
- **Oracle.lean** — new arg layout (ackRepeated + per-record action field),
  emit `repeated_window_len`, `repeated_max_fail`.
- **Manifest.lean / Contracts.lean** — #check + exact-statement pins for the new
  roles; re-pin the widened `detect_precedence`.
- **recovery.py** — enum value, constants, `_check_repeated_action_failure`,
  detect() wiring.
- **player.py** — `_handle_stuck` REPEATED branch + counter-evidence entry.
- **mutate.py** — anchors: threshold off-by-one, drop-noPlan-guard,
  flip-failure-sense, window off-by-one.
- **test_stuck_detector_diff.py** — extend encoding (action field); scenarios:
  genuine-fire, one-short, no_plan-flood-excluded, window boundary.
- **unit tests** — recovery + player handler, 100% coverage.

Gate: `formal/gate.sh` green; axioms ⊆ {propext, Classical.choice, Quot.sound}.
