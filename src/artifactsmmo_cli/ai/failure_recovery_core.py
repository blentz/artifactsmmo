"""What a repeatedly-failing action's failure means, and how long it is
blocked (Phase 5, USER 2026-10-09: "Classify by HTTP code"; proved in
`Formal.FailureRecovery`).

The REPEATED_ACTION_FAILURE recovery used to block every repeating action for
10 cycles, then 30, and then re-admit it — so a STRUCTURAL failure repeated
forever: live 2026-10-08, Robby's TaskCancel at the wrong taskmaster (HTTP 598)
was re-admitted every 10/30 cycles from 10:45 to 13:22Z. A countdown cannot
converge on a failure that elapsed time does not fix.

Four classes, by the cycle's outcome:

* LEARNED — the failure is already a model fact owned elsewhere: a lost fight
  (the learned-loss veto and the loss-risk price) and a categorical refusal or
  `already_equipped` (`refusal_fact`). No block.
* STRUCTURAL — HTTP 598, the content is not at the tile. Blocked while its
  PREMISE holds: the active-event set, the only in-process change to map
  content. No tick lifts it.
* STATE — the world differs from the belief (HTTP 404/478/497, `bank_locked`):
  a sibling took the bank stock or the order. The answer is a full refresh, not
  a block.
* TRANSPORT — anything else (network, `other`, an unexplained code): a short
  retry that expires after `TRANSPORT_RETRY_CYCLES` ticks and never escalates.
"""

from collections.abc import Mapping

from artifactsmmo_cli.ai.action_rejection import CATEGORICAL_REJECTIONS

LEARNED = "learned"
STRUCTURAL = "structural"
STATE = "state"
TRANSPORT = "transport"

TRANSPORT_RETRY_CYCLES = 10
"""Ticks a transport failure blocks its action before the retry."""

STRUCTURAL_CODES = frozenset({598})
STATE_CODES = frozenset({404, 478, 497})
_HTTP_PREFIX = "error:HTTP_"

Premise = frozenset[str]
Block = tuple[int, Premise | None]
"""(retry ticks left, premise): a TRANSPORT block carries no premise and its
ticks; a STRUCTURAL block carries its premise (the ticks are unused)."""


def failure_class(outcome: str) -> str:
    """The class of one failed cycle's outcome string (`error:...`)."""
    if outcome in ("error:fight_lost", "error:already_equipped"):
        return LEARNED
    if outcome == "error:bank_locked":
        return STATE
    if outcome.startswith(_HTTP_PREFIX):
        code = int(outcome[len(_HTTP_PREFIX):])
        if code in CATEGORICAL_REJECTIONS:
            return LEARNED
        if code in STRUCTURAL_CODES:
            return STRUCTURAL
        if code in STATE_CODES:
            return STATE
    return TRANSPORT


def record_failure(table: Mapping[str, Block], key: str, cls: str,
                   premise: Premise) -> dict[str, Block]:
    """The block table after `key` repeated a failure of class `cls`."""
    out = dict(table)
    if cls == TRANSPORT:
        out[key] = (TRANSPORT_RETRY_CYCLES, None)
    elif cls == STRUCTURAL:
        out[key] = (0, premise)
    return out


def tick(table: Mapping[str, Block]) -> dict[str, Block]:
    """One cycle later: a transport block counts down and expires at zero; a
    structural block is untouched."""
    out: dict[str, Block] = {}
    for key, (left, premise) in table.items():
        if premise is not None:
            out[key] = (left, premise)
        elif left > 1:
            out[key] = (left - 1, None)
    return out


def blocked(table: Mapping[str, Block], premise: Premise) -> frozenset[str]:
    """The keys blocked now: every transport block, and every structural block
    whose premise still holds."""
    return frozenset(key for key, (_left, recorded) in table.items()
                     if recorded is None or recorded == premise)
