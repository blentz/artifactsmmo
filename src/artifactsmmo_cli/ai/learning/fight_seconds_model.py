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
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cache
from pathlib import Path

from artifactsmmo_api_client.models.log_schema import LogSchema
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

ACTION_LOGS = (Path(__file__).resolve().parents[4] / "tests" / "test_ai" / "fixtures"
               / "action_logs.json")
"""Every entry of the account's `/my/logs` as a `KindEntry`, with the API craft
yield of every item crafted in it, captured once from the live API
(`scripts/capture_action_logs.py`): the bootstrap's kinds a player driven
against a mocked client is handed (`tests/test_ai/fixtures.BOOTSTRAP`)."""

STORE_COOLDOWNS = (Path(__file__).resolve().parents[4] / "tests" / "test_ai" / "fixtures"
                   / "store_cooldowns.json")
"""`LearningStore.fleet_action_cooldowns` of a read-only backup of the live
learning DB, captured once (`scripts/capture_store_cooldowns.py`): what an
offline world times each priced action kind by (`offline_kind_seconds`)."""

KindEntry = tuple[str, int, str | None, int]
"""`(log type, cooldown seconds, item, quantity)` of one `/my/logs` entry: a
craft's item and units made, a recycle's item and units recycled; None and 1
for every other entry (`log_kind`)."""

PRICED_KINDS: frozenset[LogType] = frozenset({
    LogType.GATHERING, LogType.CRAFTING, LogType.RECYCLING, LogType.WITHDRAW_ITEM,
    LogType.WITHDRAW_GOLD, LogType.SELL_NPC, LogType.BUY_NPC, LogType.BUY_GE})
"""Every `/my/logs` kind the pricer charges a route's action at
(`acquisition_cost._kind_actions`)."""

STORE_KINDS: Mapping[str, LogType] = {
    "GatherAction": LogType.GATHERING,
    "CraftAction": LogType.CRAFTING,
    "RecycleAction": LogType.RECYCLING,
    "WithdrawItemAction": LogType.WITHDRAW_ITEM,
    "WithdrawGoldAction": LogType.WITHDRAW_GOLD,
    "NpcSellAction": LogType.SELL_NPC,
    "NpcBuyAction": LogType.BUY_NPC,
    "GeFillSellOrderAction": LogType.BUY_GE,
}
"""The executed action class the learning store records each priced kind
under (the user's I2 ruling, 2026-10-31: "learning DB, then raise")."""

_REPR_QUANTITY = re.compile(r"×(\d+)\)$")
"""A craft's or recycle's repr ends in its quantity: `Craft(cheese×3)` is three
craft runs, `Recycle(iron_dagger×2)` two units (`CraftAction.__repr__`,
`RecycleAction.__repr__`)."""

_BATCHED = frozenset({LogType.CRAFTING.value, LogType.RECYCLING.value})
"""The kinds whose one request runs `quantity` actions, its cooldown their sum
(review I3, measured over the account's 5,000 newest entries 2026-10-31: a
craft is 5 s per craft run, a recycle 3 s per unit; a gather, a withdraw, a buy
or a sale is one action of one cooldown whatever its quantity)."""

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
    kinds: tuple[KindEntry, ...]
    """Every entry's `KindEntry`: the per-kind seconds the pricer charges a
    route's action at (`kind_seconds`)."""

    def to_json(self) -> str:
        return json.dumps({"fights": [list(f) for f in self.fights],
                           "cooldowns": list(self.cooldowns),
                           "kinds": [list(k) for k in self.kinds]})

    @classmethod
    def from_json(cls, text: str) -> "FleetBootstrap":
        data = json.loads(text)
        return cls(tuple((int(t), int(a), float(c)) for t, a, c in data["fights"]),
                   tuple(int(c) for c in data["cooldowns"]),
                   tuple((str(k), int(c), None if i is None else str(i), int(q))
                         for k, c, i, q in data["kinds"]))


def log_kind(entry: LogSchema) -> KindEntry:
    """`entry` as a `KindEntry`: a craft's or a recycle's own item and
    quantity (`content.item`, `content.quantity`), None and 1 otherwise."""
    kind = entry.type_.value
    if kind in _BATCHED:
        return kind, entry.cooldown, str(entry.content["item"]), int(entry.content["quantity"])
    return kind, entry.cooldown, None, 1


def _applications(kind: str, item: str | None, quantity: int,
                  craft_yield: Callable[[str], int]) -> Fraction:
    """The actions one entry ran: a craft's `quantity` units made over its
    item's yield per run (cheese, 2 a run, logs 2 at 5 s: one run), a
    recycle's `quantity` units, one for any other kind."""
    if kind == LogType.CRAFTING.value:
        assert item is not None
        return Fraction(quantity, craft_yield(item))
    if kind == LogType.RECYCLING.value:
        return Fraction(quantity)
    return Fraction(1)


def kind_seconds(kinds: Iterable[KindEntry],
                 craft_yield: Callable[[str], int]) -> tuple[tuple[str, Fraction], ...]:
    """The measured seconds of ONE action of each `/my/logs` entry type in
    `kinds`, sorted by type: its entries' positive cooldowns over the actions
    they ran (`_applications`, review I3: a craft or recycle request batches
    its quantity, its cooldown their sum). A type with no positive cooldown
    is absent: it was never timed."""
    seen: dict[str, tuple[Fraction, Fraction]] = {}
    for kind, cooldown, item, quantity in kinds:
        if cooldown > 0:
            seconds, runs = seen.get(kind, (Fraction(0), Fraction(0)))
            seen[kind] = (seconds + cooldown,
                          runs + _applications(kind, item, quantity, craft_yield))
    return tuple(sorted((kind, seconds / runs) for kind, (seconds, runs) in seen.items()))


StoreCooldowns = tuple[str, str, float, int]
"""`(action class, action repr, total cooldown seconds, cycles)` of one group of
the learning store's successful cycles (`LearningStore.fleet_action_cooldowns`)."""


def _store_runs(kind: LogType, action_repr: str) -> int:
    """The actions one recorded cycle of `action_repr` ran: a craft's runs or a
    recycle's units (its repr's quantity, review I3: the server's cooldown is
    5 s a craft run, 3 s a unit recycled), one for any other kind."""
    if kind not in (LogType.CRAFTING, LogType.RECYCLING):
        return 1
    match = _REPR_QUANTITY.search(action_repr)
    if match is None:
        raise ValueError(f"a recorded {kind.value} with no quantity: {action_repr}")
    return int(match.group(1))


def store_kind_seconds(rows: Iterable[StoreCooldowns]) -> tuple[tuple[str, Fraction], ...]:
    """The learned seconds of ONE action of each priced kind, sorted by kind:
    the store's recorded server cooldowns of its action class (`STORE_KINDS`)
    over the actions they ran (`_store_runs`). A kind the store never
    recorded is absent: it was never timed."""
    seen: dict[str, tuple[float, int]] = {}
    for action_class, action_repr, seconds, cycles in rows:
        kind = STORE_KINDS[action_class]
        total, runs = seen.get(kind.value, (0.0, 0))
        seen[kind.value] = (total + seconds, runs + cycles * _store_runs(kind, action_repr))
    return tuple(sorted((kind, Fraction(total) / runs) for kind, (total, runs) in seen.items()))


def learned_kind_seconds(store: LearningStore | None, bootstrap: FleetBootstrap,
                         craft_yield: Callable[[str], int]) -> tuple[tuple[str, Fraction], ...]:
    """The seconds of one action of each priced kind: the learning store's
    recorded server cooldowns (`store_kind_seconds`), read once per recorded
    cycle; the `/my/logs` bootstrap's (`kind_seconds`) only while there is no
    store or it has recorded no priced action (a fresh install). A kind
    neither timed raises where it is priced (`SelectionContext.seconds_of`)."""
    if store is not None:
        rows = store.per_recorded_cycle(
            "fleet_action_cooldowns",
            lambda: store.fleet_action_cooldowns(frozenset(STORE_KINDS)))
        if rows:
            return store_kind_seconds(rows)
    return kind_seconds(bootstrap.kinds, craft_yield)


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
    kinds: list[KindEntry] = []
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
            kinds.append(log_kind(entry))
            if entry.type_ == LogType.FIGHT and entry.cooldown > 0:
                fights.append((entry.content["fight"]["turns"], hastes[entry.character],
                               float(entry.cooldown)))
        enough = (len(fights) >= BOOTSTRAP_FIGHTS
                  and len({haste for _, haste, _ in fights}) >= spread)
        if enough or page >= result.pages:
            return FleetBootstrap(tuple(fights), tuple(cooldowns), tuple(kinds))
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


def offline_kind_seconds(path: Path = STORE_COOLDOWNS) -> tuple[tuple[str, Fraction], ...]:
    """`store_kind_seconds` of a learning-store capture (see `STORE_COOLDOWNS`)."""
    capture = json.loads(path.read_text())
    return store_kind_seconds((str(action_class), str(action_repr), float(seconds), int(cycles))
                              for action_class, action_repr, seconds, cycles in capture["rows"])


@cache
def committed_kind_seconds() -> tuple[tuple[str, Fraction], ...]:
    """`offline_kind_seconds` of the committed capture, read once per process."""
    return offline_kind_seconds()


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
                   kind_seconds=committed_kind_seconds(),
                   learned_drops=LearnedDrops.empty())
