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

    # Planning used as a feasibility test: `doomed_skip`, `doomed_mark`,
    # `doomed_clear` and `not_plannable` were retired by Phase 3-1 (every
    # candidate is asked every cycle; a walk-served goal's answer is its named
    # DECOMPOSE_DECLINE). Their values stay in `decision_events` history and
    # must not be reused.
    # Which producer answered a planning request (subject: goal repr;
    # detail: nodes_created/explored/timed_out/node_capped/plan_len).
    FAST_PATH = "fast_path"
    SEARCH = "search"
    # Why the route-driven producer declined an obtain goal it serves
    # (subject: goal repr; detail: the named reason, e.g. `no_source:<item>`,
    # `unmapped_step:<kind>:<item>:<via>`, `first_leg_inapplicable:<action>`).
    # Phase 2c-2.0: before it, a decline was silent and the caller searched.
    DECOMPOSE_DECLINE = "decompose_decline"
    # Selection-order compensations (subject: goal repr).
    WORTH_GATE_BYPASS = "worth_gate_bypass"
    WAIT_FALLBACK = "wait_fallback"
    # `servable_promotion` was retired by Phase 3-2: the root walk no longer
    # promotes past an unservable pick, it never picks one. What it names
    # instead (subject: the declined root's repr; detail: the reason its step
    # cannot be served this cycle):
    ROOT_DECLINE = "root_decline"
    # Stability between cycles (subject: goal/root repr). `aged_pick` was
    # retired by Phase 4-2b-ii with the focus-aging interleave it reported; the
    # cycle budget and its one-turn yield (INTENTION_BUDGET) replace it. Its
    # value stays in `decision_events` history and must not be reused.
    COMMITMENT_CHANGE = "commitment_change"
    GUARD_PREEMPT = "guard_preempt"
    PLAN_CACHE_HIT = "plan_cache_hit"
    COMMITMENT_KEPT = "commitment_kept"
    # The intention ended because its progress stopped moving (Phase 4-2a;
    # subject: the committed goal repr, detail: `stalled:<cycles>`).
    INTENTION_STALLED = "intention_stalled"
    # The intention ended because it spent its cycle budget, and its root
    # yields one turn (Phase 4-2b; detail: `budget:<cycles>`).
    INTENTION_BUDGET = "intention_budget"
    REPLAN = "replan"
    # Recovery by countdown (subject: signal, goal or action key).
    STUCK_SIGNAL = "stuck_signal"
    SUPPRESS = "suppress"
    ERROR_BACKOFF = "error_backoff"
    REFUSAL_POISON = "refusal_poison"
