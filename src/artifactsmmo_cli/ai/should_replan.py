"""Pure predicate: decide whether to re-run the GOAP planner this cycle or reuse
the cached plan. Kept side-effect-free so the policy is unit-testable and, later,
formally gate-able. See docs/superpowers/specs/2026-06-23-plan-cache-macro-learning-design.md."""

from artifactsmmo_cli.ai.plan_cache import PlanCache


def should_replan(
    cache: PlanCache | None,
    last_outcome: str | None,
    latch_active: bool,
    goal_satisfied: bool,
    step_applicable: bool,
    replan_interval: int,
) -> bool:
    """True => re-decide from scratch. Triggers (any):
    1. no cache (cold start)
    2. previous action did not succeed
    3. goal satisfied or plan exhausted
    4. gear-review latch armed/cleared since plan time
    5. cached run reached the staleness bound
    6. the cached step is no longer applicable
    """
    if cache is None:
        return True
    if last_outcome is not None and last_outcome != "ok":
        return True
    if goal_satisfied or cache.exhausted():
        return True
    if latch_active != cache.latch_active:
        return True
    if cache.cycles_since_replan >= replan_interval:
        return True
    if not step_applicable:
        return True
    return False
