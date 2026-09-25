"""The compensating mechanisms whose firing the decision-events log records.

Phase 0b of `docs/PLAN_decision_architecture_redesign.md`. Each value names one
mechanism the redesign intends to make unnecessary. A later phase may delete a
mechanism only after the census shows its events have gone to zero, so a
mechanism that fires silently cannot be deleted honestly. Values are stored
verbatim in `decision_events.mechanism`; renaming one splits its history.

`StuckExit` has no member: it ends the process before the cycle's events are
written, and `sessions.exit_reason = "stuck_exit"` already records it durably.
"""

from enum import StrEnum


class Mechanism(StrEnum):
    """One compensating mechanism. The event's `subject` is named per member."""

    # Planning used as a feasibility test (subject: goal repr).
    DOOMED_SKIP = "doomed_skip"
    DOOMED_MARK = "doomed_mark"
    DOOMED_CLEAR = "doomed_clear"
    NOT_PLANNABLE = "not_plannable"
    GRIND_DOOM = "grind_doom"
    # Which producer answered a planning request (subject: goal repr;
    # detail: nodes_created/explored/timed_out/node_capped/plan_len).
    FAST_PATH = "fast_path"
    SEARCH = "search"
    GRIND_SEARCH = "grind_search"
    # Selection-order compensations (subject: goal repr).
    WORTH_GATE_BYPASS = "worth_gate_bypass"
    WAIT_FALLBACK = "wait_fallback"
    SERVABLE_PROMOTION = "servable_promotion"
    # Stability between cycles (subject: goal/root repr).
    COMMITMENT_CHANGE = "commitment_change"
    GUARD_PREEMPT = "guard_preempt"
    AGED_PICK = "aged_pick"
    PLAN_CACHE_HIT = "plan_cache_hit"
    REPLAN = "replan"
    # Recovery by countdown (subject: signal, goal or action key).
    STUCK_SIGNAL = "stuck_signal"
    SUPPRESS = "suppress"
    ERROR_BACKOFF = "error_backoff"
    REFUSAL_POISON = "refusal_poison"
