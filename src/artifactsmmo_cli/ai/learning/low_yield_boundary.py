"""Pure decision boundary for the low-yield-cancel rule.

This module isolates the boolean fire condition of `low_yield_cancel_fires`
(in `projections.py`) from its impure shell — the LearningStore reads, best-
alternative pick, and projection computation. The shell fetches scalars, then
calls `low_yield_fires_pure` to get the verdict. The pure boundary mirrors the
production semantics verbatim so the Lean model in `formal/Formal/LowYieldCancel.lean`
can prove monotonicity, no-task / no-sample safety, and the explicit
zero-fast-path bypass of the confidence gate.

Design intent of the zero-fast-path (verified against
`tests/test_ai/test_low_yield_cancel.py::TestGHCharXpFastCancel`):

  When `current_xp == 0` (FarmItems has been observed and yields ZERO char-XP/
  cycle — Robby's 347-fish gudgeon scenario), ANY alternative that pays
  positive char-XP/cycle beats it immediately, regardless of confidence or
  alternative sample count, because zero is unimprovable. The 3-cycle minimum
  on the alternative comes from the natural prerequisite that `alt_samples > 0`
  for the lookup to find an alternative at all; the test seeds 3 alt cycles
  but only because that's how the test is written, not because the production
  code enforces a minimum.

This is INTENTIONAL behavior, not a defect — see test docstring quoting
"Should fire immediately — no need to wait for confidence threshold".
"""


def low_yield_fires_pure(
    has_task: bool,
    current_xp: float,
    alt_xp: float,
    confidence: float,
    farm_samples: int,
    alt_samples: int,
    margin: float = 1.5,
    min_confidence: float = 0.5,
) -> bool:
    """Pure low-yield-cancel decision.

    Mirrors `low_yield_cancel_fires` in `projections.py`:
      1. Must hold a task.
      2. Must have at least one FarmItems sample AND at least one alt sample.
      3. Either:
         (zero-fast-path) `current_xp == 0` ∧ `alt_xp > 0`, OR
         (margin gate)    `confidence ≥ min_confidence`
                          ∧ `alt_xp ≥ current_xp * margin`.

    Args:
      has_task:        Caller observed `state.task_code` set AND `task_total > 0`.
      current_xp:      `expected_yield_per_cycle("FarmItems", history).char_xp`.
      alt_xp:          `expected_yield_per_cycle(best_alt, history).char_xp`.
      confidence:      `project_task_completion(state, history).confidence`.
      farm_samples:    sample_count of the FarmItems yield.
      alt_samples:     sample_count of the best-alt yield.
      margin:          Multiplicative margin; production constant 1.5.
      min_confidence:  Confidence gate; production constant 0.5.
    """
    if not has_task:
        return False
    if farm_samples <= 0 or alt_samples <= 0:
        return False
    # Zero-char-XP fast-path: any positive alternative dominates.
    if current_xp == 0 and alt_xp > 0:
        return True
    if confidence < min_confidence:
        return False
    return alt_xp >= current_xp * margin
