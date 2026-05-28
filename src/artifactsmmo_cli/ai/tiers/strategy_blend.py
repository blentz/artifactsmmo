"""Pure cores for the Tier-3 strategy value math: the per-root skill-balancing
multiplier and the learning blend.

Extracted from `StrategyEngine._balancing` and `StrategyEngine._learned_blend`
in `strategy.py` so the SAME formulas can be:

* differentially tested against the Lean rational model
  (`formal/Formal/StrategyBlend.lean`), and
* refactored in one place without re-stating constants.

Both functions are total over their numeric inputs (no division, no NaN, no
raised exceptions). The constants below mirror the module-level constants in
`strategy.py` exactly. The live engine delegates to these helpers.
"""

# --- balancing -------------------------------------------------------------
BALANCE_K = 0.25
BALANCE_THRESHOLD = 2
BALANCE_MIN = 0.5
BALANCE_MAX = 2.0


def balancing(leader: int, current: int) -> float:
    """Per-skill balancing multiplier.

    `raw = 1 + BALANCE_K * (leader - current - BALANCE_THRESHOLD)` clamped to
    `[BALANCE_MIN, BALANCE_MAX]`. With the production constants
    (K=0.25, threshold=2, [0.5, 2.0]):

    * `leader - current = 2` (the skill sits exactly one threshold-margin behind
      the leader) ⇒ raw = 1.0, the neutral identity baseline.
    * Strictly behind the leader by more than 2 levels ⇒ multiplier above 1.
    * Equal to or ahead of the leader (gap ≤ 2) ⇒ multiplier below or equal 1,
      clamped at 0.5 once raw drops that low.

    The clamp bounds are SAFETY: no skill is ever fully downweighted (would
    starve the rest of the build) or amplified beyond 2x (would dominate every
    other category). See `formal/Formal/StrategyBlend.lean` for the bound /
    monotonicity / identity-at-threshold proofs.
    """
    raw = 1.0 + BALANCE_K * (leader - current - BALANCE_THRESHOLD)
    return max(BALANCE_MIN, min(BALANCE_MAX, raw))


# --- learned_blend ---------------------------------------------------------
LEARN_W_MAX = 0.5
LEARN_SAMPLE_FULL = 20


def blend_weight(sample_count: int) -> float:
    """Sample-driven blend weight `w ∈ [0, LEARN_W_MAX]`.

    Linear ramp `LEARN_W_MAX * min(1, sample_count / LEARN_SAMPLE_FULL)`. With
    the production constants (`LEARN_W_MAX = 0.5`, `LEARN_SAMPLE_FULL = 20`):

    * 0 samples ⇒ w = 0 (warm-up identity: blend equals the prior `value`)
    * ≥ 20 samples ⇒ w = 0.5 (full learned weight, but never more)

    Because `w ≤ 0.5 < 1`, the learned signal can never fully overwrite the
    prior — see `learned_blend` for the convex-bound consequence.
    """
    if sample_count <= 0:
        return 0.0
    return LEARN_W_MAX * min(1.0, sample_count / LEARN_SAMPLE_FULL)


def learned_blend(value: float, normalized: float, w: float) -> float:
    """Convex blend of the prior `value` with the observed `normalized` signal.

    Returns `(1 - w) * value + w * normalized`. With `w ∈ [0, 1]` (production
    pipes in `w ∈ [0, 0.5]` via `blend_weight`), the result lies between
    `value` and `normalized` inclusive — the anti-Phase-1 unbounded-bonus
    property: a learned signal can NEVER pull the blended score above the
    larger of `value` and `normalized`, nor below the smaller.

    Pre: `normalized ∈ [0, 1]` (production normalizes char-XP yield to that
    interval). The convex-bound theorem only assumes `w ∈ [0, 1]` and does not
    constrain `normalized`'s range; the [0, 1] normalization is a tighter
    invariant the caller upholds.

    See `formal/Formal/StrategyBlend.lean` for:
    * `w = 0 ⇒ blend = value` (warm-up identity)
    * `min(value, normalized) ≤ blend ≤ max(value, normalized)` (convex bound)
    * monotone non-decreasing in `normalized` (given `w ≥ 0`).
    """
    return (1 - w) * value + w * normalized
