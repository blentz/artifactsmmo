"""Drop observations from the fleet's recorded cycles (spec 2026-10-18 §2.8):
what `ai/drop_chance_core` learns a drop chance from.

An ATTEMPT at a source is one successful cycle of its action
(`LearningStore.fleet_drop_rows`): a `GatherAction` whose learning key is
`Gather(<resource>)` or `Gather(<resource>-><item>)` (one server gather each,
whichever drop the plan wanted: the server rolls the whole table), or a solo
`FightAction` `Fight(<monster>)`. A party fight `Fight(<monster>+<ally>...)` is
not the solo roll and is left out. A HIT of an item is that item in the cycle's
`drops_json` (the items the bag gained, positive deltas only). Pooled over
every character: a drop chance is a fact about the source, not the character.

The cycle's `prospecting` (recorded since 2026-10-21, NULL before) groups the
attempts for `fit_k`; `learned_drops` pools across it.

The tally is read once per recorded cycle: it is held against the store it was
read from (the store itself, so the key cannot outlive its object) and the
newest cycle id, and a newer id folds in only the rows past the last one read
(the table is append-only).

Only the CURRENT season is evidence (ruling T12f): a cycle recorded before the
season start the server reports (`GameData.season_start`, `GET /`) is no
attempt. A reset changes rates and content, and last season's sources may be
gone from this season's catalogue. Within the season, an observed source the
catalogue lacks still raises.

Inside a `LearningStore.search_cache` episode the tally and `fleet_k` are
memoised through the store (`LearningStore.cached`): the pricing walk asks for
every drop it prices, and each ask would otherwise read the newest cycle id
again and refit the slope. The `fleet_k` memo holds the catalogue it was
fitted on in its value, never an `id()` in its key, and serves only that
catalogue.
"""

import json
import re
from collections import Counter
from datetime import datetime
from fractions import Fraction

from artifactsmmo_cli.ai.drop_chance_core import fit_k
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.store import LearningStore

_GATHER = re.compile(r"Gather\(([^()]+?)(?:->[^()]+)?\)")
_FIGHT = re.compile(r"Fight\(([^()+]+)(\+[^()]+)?\)")

Key = tuple[str, str, int | None]
"""`(action_class, source, prospecting)` of a group of attempts."""

Tally = tuple[Counter[Key], dict[Key, Counter[str]]]
"""Attempts per group, and each group's hits per item."""

_COUNTS: list[tuple[LearningStore, datetime, int, Tally]] = []
"""The last tally: its store (held, see the module doc), the season start it
reads from, the newest cycle id folded in, and the tally."""


def _source(action_class: str, action_repr: str) -> str | None:
    """The source an attempt rolled at, or None for a party fight."""
    if action_class == "GatherAction":
        gather = _GATHER.fullmatch(action_repr)
        if gather is None:
            raise ValueError(f"a gather with no resource in its learning key: {action_repr}")
        return gather.group(1)
    fight = _FIGHT.fullmatch(action_repr)
    if fight is None:
        raise ValueError(f"a fight with no monster in its learning key: {action_repr}")
    if fight.group(2) is not None:
        return None
    return fight.group(1)


def _fold(tally: Tally, rows: list[tuple[str, str, int | None, str | None]]) -> None:
    attempts, hits = tally
    for action_class, action_repr, prospecting, drops_json in rows:
        source = _source(action_class, action_repr)
        if source is None:
            continue
        key = (action_class, source, prospecting)
        attempts[key] += 1
        drops = json.loads(drops_json) if drops_json else {}
        hits.setdefault(key, Counter()).update(drops.keys())


def _tally(store: LearningStore, since: datetime) -> Tally:
    """The fleet's attempts and hits since `since` through the newest cycle,
    read once per search episode."""
    return store.cached(("drop_tally", since), lambda: _read_tally(store, since))


def _read_tally(store: LearningStore, since: datetime) -> Tally:
    last = store.last_cycle_id()
    # A newest id below the one last read means the table was replaced or
    # pruned under this store: the tally is read afresh, as it is for a new
    # season start.
    if (_COUNTS and _COUNTS[0][0] is store and _COUNTS[0][1] == since
            and _COUNTS[0][2] <= last):
        _, _, seen, tally = _COUNTS[0]
        if seen == last:
            return tally
    else:
        seen, tally = 0, (Counter(), {})
    _fold(tally, store.fleet_drop_rows(seen, last, since))
    _COUNTS[:] = [(store, since, last, tally)]
    return tally


def learned_drops(store: LearningStore, game_data: GameData) -> LearnedDrops:
    """This cycle's drop evidence (ruling T16a): the `(attempts, hits)` of
    every observed `(source, item)` this season (`game_data.season_start`),
    pooled over the fleet and every prospecting, and the fleet's slope
    (`fleet_k`). Both read through the per-episode memo; nothing here is a
    second one."""
    attempts, hits = _tally(store, game_data.season_start)
    per_source: Counter[str] = Counter()
    per_drop: Counter[tuple[str, str]] = Counter()
    for key, count in attempts.items():
        source = key[1]
        per_source[source] += count
        for item, hit in hits[key].items():
            per_drop[source, item] += hit
    return LearnedDrops(tuple(sorted(per_source.items())), tuple(sorted(per_drop.items())),
                        fleet_k(store, game_data))


def _drop_table(game_data: GameData, action_class: str,
                source: str) -> list[tuple[str, int, int, int]]:
    """The catalogue's `(item, rate, min, max)` rows of `source`; raises for a
    source the catalogue does not know (no rate to learn against)."""
    if action_class == "GatherAction":
        if source not in game_data.resource_drops_full:
            raise ValueError(f"resource {source} has no drop table in the catalogue")
        return game_data.resource_drop_table(source)
    if source not in game_data.monster_levels:
        raise ValueError(f"monster {source} has no drop table in the catalogue")
    return game_data.monster_drops(source)


def fleet_k(store: LearningStore, game_data: GameData) -> Fraction:
    """The fleet's prospecting slope `k` (`drop_chance_core.fit_k`), on one
    sample per (source, item, prospecting): every drop in the catalogue table of
    each observed source, at its API rate. Attempts without a recorded
    prospecting are no sample.

    A drop at API rate 1 is no sample either (ruling T11e): its chance is capped
    at 1 for every `k >= 0`, so its observed ratio is 1 whatever `k` is. It
    carries nothing about the slope, yet it would add `attempts·P²` to the
    denominator and pull `k` toward 0 with full weight.

    Fitted once per search episode and catalogue: the memo's value holds the
    catalogue it was fitted on, and another catalogue is fitted afresh."""
    fitted_on, k = store.cached(("fleet_k",), lambda: (game_data, _fleet_k(store, game_data)))
    if fitted_on is not game_data:
        return _fleet_k(store, game_data)
    return k


def _fleet_k(store: LearningStore, game_data: GameData) -> Fraction:
    attempts, hits = _tally(store, game_data.season_start)
    samples: list[tuple[int, int, int, int]] = []
    for key, count in attempts.items():
        action_class, source, prospecting = key
        if prospecting is None:
            continue
        samples.extend((rate, prospecting, count, hits[key][item])
                       for item, rate, _, _ in _drop_table(game_data, action_class, source)
                       if rate > 1)
    return fit_k(samples)
