"""Pure decision core for `task_decision` (extracted for formal verification).

`task_decision_pure` consumes ONLY scalar inputs — no `WorldState`, no
`LearningStore`, no `GameData`. The caller (`task_decision` in
`task_decision.py`) is responsible for resolving:

  * `req_is_none` — `task_requirement(...) is None`
    (already-feasible OR `task_total == 0`).
  * `req_is_combat` — req is not None ∧ `req.skill == "combat"`.
  * `history_present` — `history is not None`.
  * `skill_up_vpc` — `reward / total_cycles` (computed by caller; the caller
    establishes `total_cycles ≥ 1` from the cross-file invariant that
    `task_requirement` returns None when `task_total == 0`, which is why
    `req_is_none == False` lets the caller divide).
  * `baseline_vpc` — `DEFAULT_COIN_VALUE_GOLD` (5.0).
  * `confidence_margin` — `LOW_CONFIDENCE_MARGIN` (3.0).
  * `confidence` — `SkillXpCurve.confidence(...)`, a value in [0, 1].

The decision (PURSUE | PIVOT) is then EXACTLY:

  * `req_is_none`                                 → PURSUE
  * `req_is_combat or not history_present`        → PIVOT
  * `skill_up_vpc >= baseline_vpc * (1 + confidence_margin * (1 - confidence))`
                                                  → PURSUE
  * otherwise                                     → PIVOT

This module is the formalisation target. The Lean model in
`formal/Formal/TaskDecision.lean` mirrors it over ℚ.
"""

from artifactsmmo_cli.ai.task_decision_labels import PIVOT, PURSUE


def required_vpc(baseline_vpc: float, confidence_margin: float,
                 confidence: float) -> float:
    """The minimum value-per-cycle the skill-up path must beat to be picked.

    `required = baseline * (1 + margin * (1 - confidence))`. Decreasing in
    confidence (higher confidence ⇒ lower bar). Mirrors the formula in
    `task_decision.py`."""
    return baseline_vpc * (1.0 + confidence_margin * (1.0 - confidence))


def task_decision_pure(req_is_none: bool, req_is_combat: bool,
                       history_present: bool,
                       skill_up_vpc: float, baseline_vpc: float,
                       confidence_margin: float, confidence: float) -> str:
    """Pure decision: PURSUE vs PIVOT. See module docstring for inputs."""
    if req_is_none:
        return PURSUE
    if req_is_combat or not history_present:
        return PIVOT
    return PURSUE if skill_up_vpc >= required_vpc(
        baseline_vpc, confidence_margin, confidence) else PIVOT
