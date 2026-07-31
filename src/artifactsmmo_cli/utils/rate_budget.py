"""Rate-limit budgets: parse /my/rates and divide it across concurrent children.

ArtifactsMMO applies standard rate limits PER IP ADDRESS, so every `play --all`
child draws from one shared budget. The parent reads the live limits once and
hands each child its share; nothing here hardcodes a limit value, per the
project's use-only-API-data rule.
"""

import json
from dataclasses import asdict, dataclass
from typing import Any, cast

_WINDOWS = ("second", "minute", "hour", "day")
_BUCKETS = ("account", "data", "action")


@dataclass(frozen=True)
class WindowBudget:
    """Per-window request allowance. None means the API declares no limit."""

    second: int | None
    minute: int | None
    hour: int | None
    day: int | None

    def divided_by(self, children: int) -> "WindowBudget":
        def share(limit: int | None) -> int | None:
            if limit is None:
                return None
            return max(1, limit // children)

        return WindowBudget(
            second=share(self.second),
            minute=share(self.minute),
            hour=share(self.hour),
            day=share(self.day),
        )

    def as_windows(self) -> dict[float, int]:
        """{window length in seconds: limit}, omitting undeclared windows."""
        spans = {"second": 1.0, "minute": 60.0, "hour": 3600.0, "day": 86400.0}
        return {
            spans[name]: limit
            for name in _WINDOWS
            if (limit := getattr(self, name)) is not None
        }


@dataclass(frozen=True)
class BucketBudgets:
    """The three buckets this client uses. `simulation` and `assistant` are
    member-only and unused by the bot, so they are deliberately not modelled."""

    account: WindowBudget
    data: WindowBudget
    action: WindowBudget

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @staticmethod
    def from_json(text: str) -> "BucketBudgets":
        raw = cast(dict[str, Any], json.loads(text))
        return BucketBudgets(
            **{bucket: WindowBudget(**cast(dict[str, Any], raw[bucket])) for bucket in _BUCKETS}
        )


def parse_rate_limits(payload: dict[str, Any]) -> BucketBudgets:
    """Build budgets from a /my/rates response body. Raises on a missing bucket
    rather than defaulting: an unreadable budget must fail loudly, not silently
    become an unlimited one."""
    data = cast(dict[str, Any], payload.get("data"))
    if data is None:
        raise ValueError("rate limit payload has no 'data' envelope")
    parsed: dict[str, WindowBudget] = {}
    for bucket in _BUCKETS:
        scope = data.get(bucket)
        if scope is None:
            raise ValueError(f"rate limit payload has no {bucket!r} bucket")
        scope_dict = cast(dict[str, Any], scope)
        window_dict: dict[str, int | None] = {}
        for window in _WINDOWS:
            window_data = cast(dict[str, Any] | None, scope_dict.get(window))
            limit: int | None = None
            if window_data is not None:
                limit = cast(int | None, window_data.get("limit"))
            window_dict[window] = limit
        parsed[bucket] = WindowBudget(**window_dict)
    return BucketBudgets(**parsed)


def split_budget(budgets: BucketBudgets, children: int) -> BucketBudgets:
    """Each child's share. Floors, but never to zero — a child with a zero
    allowance would block forever instead of merely being slow."""
    if children < 1:
        raise ValueError(f"children must be >= 1, got {children}")
    return BucketBudgets(
        account=budgets.account.divided_by(children),
        data=budgets.data.divided_by(children),
        action=budgets.action.divided_by(children),
    )
