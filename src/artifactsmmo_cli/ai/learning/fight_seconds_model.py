"""The learned fight-seconds model and the learned seconds of one planner action
(spec 2026-10-18 §2.9, rulings CA and CC).

A fight's seconds are `fight_seconds_core.fight_seconds` at its expected turns
and the fighter's haste, with `(s_turn, h, floor)` fitted
(`fight_seconds_core.fit`) to observed fights:

* the fleet's recorded fights (`LearningStore.fleet_fight_samples`: every
  cycle that stored its server `fight.turns` beside its cooldown), and
* a bootstrap from the server's own history of the whole account
  (`GET /my/logs`, whose fight entries carry `turns`, the cooldown and the
  character), so the fit starts from data on a store that has not yet
  recorded a fight's length (`fetch_fleet_bootstrap`, ruling ZD). The fleet
  fetches it once: `play --all` before its children start, a lone `play` or
  `plan` at its own start. A character's own log is not enough: one that has
  only gathered lately holds no fight, and its fit raised at startup (live
  2026-10-20, R2D2 and C3P0).

The seconds of one planner ACTION (the unit the acquisition walk counts in) are
the store's mean cooldown over every executed action
(`LearningStore.fleet_mean_action_seconds`), or the bootstrap's while the
store has recorded none. With no observation of either, the answer raises: no
constant stands in for it.

Offline worlds (tests, scenarios, censuses) fit the same way from a committed
capture of the live `/my/logs` (`FIGHT_LOGS`, written once by
`scripts/capture_fight_logs.py`).
"""

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cache
from pathlib import Path

from artifactsmmo_api_client.models.log_type import LogType

from artifactsmmo_cli.ai.fight_seconds_core import (
    NO_FIGHTS,
    FightSecondsModel,
    FitSums,
    fit_sums,
    solve,
)
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.api_wrapper import APIWrapper

FIGHT_LOGS = (Path(__file__).resolve().parents[4] / "tests" / "test_ai" / "fixtures"
              / "fight_logs.json")
"""Every `/my/logs` entry of every fleet character, captured once from the live
API (2026-10-19), with each character's sheet haste at capture time."""

LogEntry = tuple[str, int, int | None]
"""`(type, cooldown seconds, fight turns or None)` of one `/my/logs` entry."""

Sample = tuple[int, int, float]
"""`(turns, haste, cooldown)` of one observed fight."""


def model_of(sums: FitSums) -> FightSecondsModel:
    """The model `solve`d from `sums`; raises with no positive cooldown."""
    s_turn, h, floor = solve(sums)
    return FightSecondsModel(s_turn, h, floor, len(sums.hastes) > 1, sums.kept)


def fit_model(samples: Sequence[Sample]) -> FightSecondsModel:
    """The model fitted to `samples`; raises with no positive cooldown."""
    return model_of(fit_sums(samples))


def log_fights(haste: int, entries: Iterable[LogEntry]) -> list[Sample]:
    """The fights among `entries`, each at the character's `haste`. The log
    does not carry the haste a fight was fought at; the sheet's at fetch time
    stands for it."""
    return [(turns, haste, float(cooldown)) for _, cooldown, turns in entries
            if turns is not None]


BOOTSTRAP_PAGE = 100
"""Entries per `/my/logs` page: the API's largest page, so the fewest requests."""

BOOTSTRAP_FIGHTS = 50
"""Fights with a positive cooldown the bootstrap pages for before it stops.
Two parameters are fitted on them (`s_turn`, `h`) and the committed capture
fits at R² 0.9998 on 1,180, so 50 leaves the fit well determined while one
page usually holds them."""

_HASTE_SPREAD = 2
"""Distinct hastes the bootstrap's fights must span when the fleet has them:
one haste cannot tell `h` from `s_turn` (`FightSecondsModel.haste_identified`)."""


@dataclass(frozen=True)
class FleetBootstrap:
    """The account log's observations for the fit: its fights as `Sample`s and
    every entry's cooldown (the action-seconds bootstrap)."""

    fights: tuple[Sample, ...]
    cooldowns: tuple[int, ...]

    def to_json(self) -> str:
        return json.dumps({"fights": [list(f) for f in self.fights],
                           "cooldowns": list(self.cooldowns)})

    @classmethod
    def from_json(cls, text: str) -> "FleetBootstrap":
        data = json.loads(text)
        return cls(tuple((int(t), int(a), float(c)) for t, a, c in data["fights"]),
                   tuple(int(c) for c in data["cooldowns"]))


def fetch_fleet_bootstrap(api: APIWrapper, hastes: Mapping[str, int],
                          acquire: Callable[[], None]) -> FleetBootstrap:
    """The account's `/my/logs`, newest first, paged until its fights with a
    positive cooldown number `BOOTSTRAP_FIGHTS` and span `_HASTE_SPREAD`
    hastes (or every haste in `hastes`, when the fleet has fewer), or until
    the log runs out. Each fight is at its character's sheet haste in
    `hastes`: the log does not carry the haste a fight was fought at. An
    entry of a character not in `hastes` is left out.
    `acquire` charges each request to the account bucket."""
    spread = min(_HASTE_SPREAD, len(set(hastes.values())))
    fights: list[Sample] = []
    cooldowns: list[int] = []
    page = 1
    while True:
        acquire()
        result = api.get_all_characters_logs(page=page, size=BOOTSTRAP_PAGE)
        for entry in result.data:
            if entry.character not in hastes:
                # Off the roster (a deleted or renamed character): no sheet,
                # so no haste to put its fights at, and not this fleet's.
                continue
            cooldowns.append(entry.cooldown)
            if entry.type_ == LogType.FIGHT and entry.cooldown > 0:
                fights.append((entry.content["fight"]["turns"], hastes[entry.character],
                               float(entry.cooldown)))
        enough = (len(fights) >= BOOTSTRAP_FIGHTS
                  and len({haste for _, haste, _ in fights}) >= spread)
        if enough or page >= result.pages:
            return FleetBootstrap(tuple(fights), tuple(cooldowns))
        page += 1


_LEARNED: list[tuple[LearningStore, int, FitSums, tuple[Sample, ...], FightSecondsModel]] = []
"""The last fit: its store (held, so the key cannot outlive its object), the
newest cycle id folded in, the sums of the store's recorded fights through it,
the bootstrap, and the model."""


def learned_model(store: LearningStore, bootstrap: Sequence[Sample]) -> FightSecondsModel:
    """The model fitted to the fleet's recorded fights and `bootstrap`.

    Read once per recorded cycle: the fit is held against its store and the
    newest cycle id, and a newer id folds in only the fights recorded past the
    last one read (the table is append-only) into the held sums
    (`fit_sums`), so the model equals a cold fit of every recorded fight and
    the bootstrap, without re-reading or re-summing them."""
    last = store.last_cycle_id()
    key = tuple(bootstrap)
    # Only a newest id that dropped below the one last read is detected: the
    # table was replaced under this store (newest id dropped), and the fights
    # are read afresh. Rows removed below the newest id are not detected.
    held = _LEARNED[0] if _LEARNED and _LEARNED[0][0] is store and _LEARNED[0][1] <= last else None
    if held is not None and held[1] == last and held[3] == key:
        return held[4]
    seen, recorded = (held[1], held[2]) if held is not None else (0, NO_FIGHTS)
    recorded = fit_sums(store.fleet_fight_samples(seen, last), recorded)
    model = model_of(fit_sums(key, recorded))
    _LEARNED[:] = [(store, last, recorded, key, model)]
    return model


_MEAN: list[tuple[LearningStore, int, float | None]] = []
"""The last mean action seconds read: its store (held), the newest cycle id it
was read at, and the mean."""


def _fleet_mean(store: LearningStore) -> float | None:
    """`store.fleet_mean_action_seconds()`, read once per recorded cycle (the
    table is append-only, so an unchanged newest id is an unchanged mean)."""
    last = store.last_cycle_id()
    if not (_MEAN and _MEAN[0][0] is store and _MEAN[0][1] == last):
        _MEAN[:] = [(store, last, store.fleet_mean_action_seconds())]
    return _MEAN[0][2]


def _mean_cooldown(cooldowns: Iterable[int], source: str) -> Fraction:
    positive = [cooldown for cooldown in cooldowns if cooldown > 0]
    if not positive:
        raise ValueError(f"{source}: no action with a cooldown")
    return Fraction(sum(positive), len(positive))


def learned_action_seconds(store: LearningStore, bootstrap: Iterable[int]) -> Fraction:
    """The fleet's mean seconds per executed action, or the `bootstrap`
    cooldowns' while the store has recorded none; raises with neither."""
    mean = _fleet_mean(store)
    if mean is not None:
        return Fraction(mean)
    return _mean_cooldown(bootstrap, "no executed action is recorded and the bootstrap has")


def timing_of(store: LearningStore | None,
              bootstrap: FleetBootstrap) -> tuple[FightSecondsModel, Fraction]:
    """The fight-seconds model and the seconds of one action: fitted with the
    store's fleet record when there is a store, on the account-log
    `bootstrap` alone when there is none."""
    if store is None:
        seconds = _mean_cooldown(bootstrap.cooldowns, "the /my/logs bootstrap")
        return fit_model(bootstrap.fights), seconds
    return learned_model(store, bootstrap.fights), learned_action_seconds(store,
                                                                        bootstrap.cooldowns)


def offline_timing(path: Path = FIGHT_LOGS) -> tuple[FightSecondsModel, Fraction]:
    """The model and the seconds of one action fitted to a `/my/logs` capture
    (see `FIGHT_LOGS`): what an offline world reads where a live store is."""
    capture = json.loads(path.read_text())
    samples: list[Sample] = []
    cooldowns: list[int] = []
    for character in capture["characters"].values():
        entries = [(kind, cooldown, turns) for kind, cooldown, turns in character["entries"]]
        samples.extend(log_fights(character["haste"], entries))
        cooldowns.extend(cooldown for _, cooldown, _ in entries)
    seconds = _mean_cooldown(cooldowns, str(path))
    return fit_model(samples), seconds


@cache
def committed_timing() -> tuple[FightSecondsModel, Fraction]:
    """`offline_timing` of the committed capture, fitted once per process."""
    return offline_timing()


def offline_context(ctx: SelectionContext) -> SelectionContext:
    """`ctx` carrying the committed capture's timing and no observed drops: the
    context an offline world (scenario, census) prices in. An offline world
    has no learning store, so every drop is at its API prior
    (`LearnedDrops.empty()`, ruling T16a)."""
    model, seconds = committed_timing()
    return replace(ctx, fight_seconds=model, action_seconds=seconds,
                   learned_drops=LearnedDrops.empty())
