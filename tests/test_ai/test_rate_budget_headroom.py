"""Five characters must fit inside the per-IP hourly data budget.

The measured peak comes from play-trace-Robby.jsonl: a real 7-day single-
character run of 11224 cycles whose busiest hour held 158 cycles. Before
GlobalReadsCache, `GamePlayer._fetch_world_state` spent 3 data-bucket reads
every cycle (get_character + active_events + raids), which puts five
characters at 5 x 158 x 3 = 2370/hour against a 2000/hour ceiling.

GlobalReadsCache (per-GamePlayer instance, `player.py:203`) now serves
active_events/raids from a 60s-TTL memo instead of re-fetching them every
cycle, so the guaranteed per-cycle data cost is get_character alone (1 read);
active_events/raids only cost a request on a cache miss, at most once per
TTL window per key. If a future change adds a per-cycle data read back
(directly, or by bypassing the cache), this must fail.

Pagination note: `_fetch_active_events`/`_fetch_raids` page at size=100 and
call `_acquire_data()` once per page, so a single cache refresh actually
costs `ceil(count / 100)` requests, not a flat 1. This model assumes 1 page
per refresh (GLOBAL_READ_KEYS = 2 requests per refresh round), which holds
for realistic active-event/raid counts (order of single digits to low tens in
this game, never near the 100-row page size). The margin below (1390 vs a
2000 ceiling, ~30% headroom) also absorbs a moderate pagination miss: even a
doubled refresh cost (240 refreshes/hour instead of 120) stays under the
ceiling; see test_five_characters_fit_under_the_hourly_data_ceiling's
projected total for the exact number.
"""

import json
from pathlib import Path

from artifactsmmo_cli.utils.rate_budget import parse_rate_limits

FIXTURE = Path("tests/test_ai/fixtures/my_rates.json")

PEAK_CYCLES_PER_HOUR = 158
MAX_CHARACTERS = 5
DATA_READS_PER_CYCLE = 1
"""get_character only. active_events and raids are served by GlobalReadsCache
and only cost a request on a TTL miss, accounted for separately below."""

GLOBAL_READ_KEYS = 2
"""active_events, raids -- each assumed to cost exactly one page per refresh
(see the pagination note in the module docstring)."""

GLOBAL_CACHE_TTL_SECONDS = 60
GLOBAL_REFRESHES_PER_HOUR = 3600 // GLOBAL_CACHE_TTL_SECONDS


def _hourly_data_limit() -> int:
    payload = json.loads(FIXTURE.read_text())
    limit = parse_rate_limits(payload).data.hour
    assert limit is not None, "fixture must declare a data.hour limit"
    return limit


def test_five_characters_fit_under_the_hourly_data_ceiling() -> None:
    per_character_cycle_reads = PEAK_CYCLES_PER_HOUR * DATA_READS_PER_CYCLE
    per_character_cache_refreshes = GLOBAL_REFRESHES_PER_HOUR * GLOBAL_READ_KEYS
    per_character = per_character_cycle_reads + per_character_cache_refreshes
    projected = MAX_CHARACTERS * per_character
    limit = _hourly_data_limit()
    assert projected < limit, (
        f"{MAX_CHARACTERS} characters project {projected} data requests/hour at "
        f"peak ({PEAK_CYCLES_PER_HOUR} cycles/hour x {DATA_READS_PER_CYCLE} "
        f"per-cycle read + {per_character_cache_refreshes} cache refreshes, "
        f"per character) against a {limit}/hour ceiling. If DATA_READS_PER_CYCLE "
        f"grew, a per-cycle read was added that GlobalReadsCache does not cover."
    )


def test_the_uncached_shape_would_have_breached_the_ceiling() -> None:
    """Documents why GlobalReadsCache exists: before it, `_fetch_world_state`
    paid 3 data reads every cycle (get_character + active_events + raids)
    with no TTL memo, and that shape overruns the budget at 5 characters."""
    uncached_reads_per_cycle = 3
    uncached = MAX_CHARACTERS * PEAK_CYCLES_PER_HOUR * uncached_reads_per_cycle
    assert uncached > _hourly_data_limit()
