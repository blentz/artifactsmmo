"""The learned fight-seconds model and the learned seconds of one planner action
(spec 2026-10-18 §2.9, rulings CA and CC).

A fight's seconds are `fight_seconds_core.fight_seconds` at its expected turns
and the fighter's haste, with `(s_turn, h, floor)` fitted
(`fight_seconds_core.fit`) to observed fights:

* the fleet's recorded fights (`LearningStore.fleet_fight_samples`: every
  cycle that stored its server `fight.turns` beside its cooldown), and
* a bootstrap from the server's own history (`GET /my/logs/{name}`, whose fight
  entries carry `turns` and the cooldown), so the fit starts from data on a
  store that has not yet recorded a fight's length.

The seconds of one planner ACTION (the unit the acquisition walk counts in) are
the store's mean cooldown over every executed action
(`LearningStore.fleet_mean_action_seconds`). With no observation of either,
the answer raises: no constant stands in for it.

Offline worlds (tests, scenarios, censuses) fit the same way from a committed
capture of the live `/my/logs` (`FIGHT_LOGS`, written once by
`scripts/capture_fight_logs.py`).
"""

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from artifactsmmo_api_client.models.log_type import LogType

from artifactsmmo_cli.ai.fight_seconds_core import fight_seconds, fit
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.api_wrapper import APIWrapper

FIGHT_LOGS = (Path(__file__).resolve().parents[4] / "tests" / "test_ai" / "fixtures"
              / "fight_logs.json")
"""Every `/my/logs` entry of every fleet character, captured once from the live
API (2026-10-19), with each character's sheet haste at capture time."""

LogEntry = tuple[str, int, int | None]
"""`(type, cooldown seconds, fight turns or None)` of one `/my/logs` entry."""

Sample = tuple[int, int, float]
"""`(turns, haste, cooldown)` of one observed fight."""


@dataclass(frozen=True)
class FightSecondsModel:
    """`(s_turn, h, floor)` fitted to `samples` observed fights.
    `haste_identified` is False when every observation had the same haste: `h`
    is then 0 and `s_turn` the seconds per turn at that haste."""

    s_turn: Fraction
    h: Fraction
    floor: Fraction
    haste_identified: bool
    samples: int

    def seconds(self, turns: Fraction, haste: int) -> Fraction:
        """A fight's seconds at `turns` (expected) for a fighter with `haste`."""
        return fight_seconds(turns, self.s_turn, self.h, haste, self.floor)


def fit_model(samples: Sequence[Sample]) -> FightSecondsModel:
    """The model fitted to `samples`; raises with no positive cooldown."""
    s_turn, h, floor = fit(samples)
    kept = [haste for _, haste, cooldown in samples if cooldown > 0]
    return FightSecondsModel(s_turn, h, floor, len(set(kept)) > 1, len(kept))


def log_fights(haste: int, entries: Iterable[LogEntry]) -> list[Sample]:
    """The fights among `entries`, each at the character's `haste`. The log
    does not carry the haste a fight was fought at; the sheet's at fetch time
    stands for it."""
    return [(turns, haste, float(cooldown)) for _, cooldown, turns in entries
            if turns is not None]


def fetch_log_entries(api: APIWrapper, name: str) -> list[LogEntry]:
    """The newest page of `name`'s `/my/logs` (one request)."""
    result = api.get_character_logs(name, page=1, size=100)
    return [(str(entry.type_), entry.cooldown,
             entry.content["fight"]["turns"] if entry.type_ == LogType.FIGHT else None)
            for entry in result.data]


_LEARNED: list[tuple[LearningStore, int, tuple[Sample, ...], FightSecondsModel]] = []
"""The last fit: its store (held, so the key cannot outlive its object), the
store's fight count, the bootstrap, and the model."""


def learned_model(store: LearningStore, bootstrap: Sequence[Sample]) -> FightSecondsModel:
    """The model fitted to the fleet's recorded fights and `bootstrap`, refitted
    only when either changed."""
    recorded = store.fleet_fight_samples()
    key = tuple(bootstrap)
    if _LEARNED and _LEARNED[0][0] is store and _LEARNED[0][1:3] == (len(recorded), key):
        return _LEARNED[0][3]
    model = fit_model([*recorded, *bootstrap])
    _LEARNED[:] = [(store, len(recorded), key, model)]
    return model


def learned_action_seconds(store: LearningStore) -> Fraction:
    """The fleet's mean seconds per executed action; raises when none is
    recorded."""
    mean = store.fleet_mean_action_seconds()
    if mean is None:
        raise ValueError("no executed action with a cooldown is recorded: the seconds "
                         "of one planner action are not learned")
    return Fraction(mean)


def offline_timing(path: Path = FIGHT_LOGS) -> tuple[FightSecondsModel, Fraction]:
    """The model and the seconds of one action fitted to a `/my/logs` capture
    (see `FIGHT_LOGS`): what an offline world reads where a live store is."""
    capture = json.loads(path.read_text())
    samples: list[Sample] = []
    cooldowns: list[int] = []
    for character in capture["characters"].values():
        entries = [(kind, cooldown, turns) for kind, cooldown, turns in character["entries"]]
        samples.extend(log_fights(character["haste"], entries))
        cooldowns.extend(cooldown for _, cooldown, _ in entries if cooldown > 0)
    if not cooldowns:
        raise ValueError(f"{path}: no action with a cooldown")
    return fit_model(samples), Fraction(sum(cooldowns), len(cooldowns))
