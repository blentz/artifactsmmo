"""Pure predicate: decide whether to re-run the GOAP planner this cycle or reuse
the cached plan. Kept side-effect-free so the policy is unit-testable and, later,
formally gate-able. See docs/superpowers/specs/2026-06-23-plan-cache-macro-learning-design.md."""

from artifactsmmo_cli.ai.plan_cache import PlanCache


def should_replan(
    cache: PlanCache | None,
    last_outcome: str | None,
    level: int,
    goal_satisfied: bool,
    step_applicable: bool,
    replan_interval: int,
) -> bool:
    """True => re-decide from scratch. Triggers (any):
    1. no cache (cold start)
    2. previous action did not succeed (a lost fight is one)
    3. goal satisfied or plan exhausted
    4. the character's level changed since plan time
    5. cached run reached the staleness bound
    6. the cached step is no longer applicable

    Trigger 4 was the RegearEdge latch (armed on a level-up or a lost fight,
    cleared when no craftable upgrade remained) until Phase 4-3b: a level-up
    is a re-rank FACT, read here off the state, and a lost fight is already
    trigger 2.
    """
    if cache is None:
        return True
    if last_outcome is not None and last_outcome != "ok":
        return True
    if goal_satisfied or cache.exhausted():
        return True
    if level != cache.plan_level:
        return True
    if cache.cycles_since_replan >= replan_interval:
        return True
    return not step_applicable


def refresh_only(
    cache: PlanCache | None,
    last_outcome: str | None,
    level: int,
    goal_satisfied: bool,
    step_applicable: bool,
    replan_interval: int,
) -> bool:
    """True when the ONLY reason to re-decide is the staleness bound (trigger 5):
    the plan is live, its last step succeeded and its next step still applies.
    Then a re-decide that picks the same goal keeps the committed plan (Phase
    2d-L1c): re-walking mid-plan does not converge, since a shrunken deficit can
    make an earlier route usable that spends a scarce unit the plan needed."""
    return (cache is not None
            and (last_outcome is None or last_outcome == "ok")
            and not goal_satisfied and not cache.exhausted()
            and level == cache.plan_level
            and cache.cycles_since_replan >= replan_interval
            and step_applicable)
