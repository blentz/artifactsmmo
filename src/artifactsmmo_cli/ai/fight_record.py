"""Fight transcript value objects.

The fight API returns a full per-turn transcript (`CharacterFightSchema.logs`)
that the bot otherwise discards. `FightRecord` is the frozen capture of one
fight, built from either the live fight response or a `/my/logs` history entry.

The transcript is treated as OPAQUE PROSE: it is server-rendered English and is
stored and displayed verbatim. Nothing is parsed out of it — every derived
number on this record comes from a structured schema field. See D4 in
docs/superpowers/specs/2026-07-27-fight-log-tui-design.md.
"""

import datetime
from typing import Any

from artifactsmmo_api_client.models.character_fight_data_schema import (
    CharacterFightDataSchema,
)
from pydantic import BaseModel, ConfigDict


def _normalise(stamp: str) -> str:
    """Round-trip a server timestamp so both sources key identically.

    `datetime.fromisoformat` accepts the `Z` suffix on Python 3.11+, so this
    needs no third-party parser — and stdlib keeps the module free of the
    untyped `dateutil` import.
    """
    return datetime.datetime.fromisoformat(stamp).isoformat()


class FightDrop(BaseModel):
    """One item dropped by a fight."""

    model_config = ConfigDict(frozen=True)

    code: str
    quantity: int


class FightRecord(BaseModel):
    """One captured fight: structured outcome plus the verbatim transcript."""

    model_config = ConfigDict(frozen=True)

    # Server-side fight time, normalised through isoparse().isoformat(). This is
    # the record's IDENTITY: the live fight response and the corresponding
    # /my/logs entry carry the same value, so merging the two sources dedupes
    # exactly, with no clock-skew guessing and no content hashing.
    started_at: str
    result: str                      # "win" | "loss"
    turns: int
    opponent: str
    logs: tuple[str, ...]            # verbatim server prose
    # Pre-fight HP. Available live (the player's own state); NOT available from
    # /my/logs, which carries only final_hp — the starting value appears solely
    # in the "Fight start:" prose line, which we do not parse. Rendered as "?"
    # rather than defaulted, so a backfilled row never claims a number the API
    # did not give us.
    hp_before: int | None
    hp_after: int
    xp: int
    gold: int
    drops: tuple[FightDrop, ...]

    @classmethod
    def from_fight_response(
        cls, data: CharacterFightDataSchema, character: str, hp_before: int,
    ) -> "FightRecord":
        """Build from a live POST /my/{name}/action/fight response."""
        fight = data.fight
        row = next(
            (c for c in fight.characters if c.character_name == character), None)
        if row is None:
            raise RuntimeError(
                f"fight response has no result row for character {character!r}")
        return cls(
            started_at=_normalise(data.cooldown.started_at.isoformat()),
            result=fight.result.value,
            turns=fight.turns,
            opponent=fight.opponent,
            logs=tuple(fight.logs),
            hp_before=hp_before,
            hp_after=row.final_hp,
            xp=row.xp,
            gold=row.gold,
            drops=tuple(
                FightDrop(code=d.code, quantity=d.quantity) for d in row.drops),
        )

    @classmethod
    def from_log_entry(cls, content: dict[str, Any], character: str) -> "FightRecord":
        """Build from the `content` of a GET /my/logs/{name} entry of type fight.

        `LogSchema.content` is typed `Any` by the generated client and arrives as
        a plain dict, so this path indexes rather than attribute-accesses.
        """
        fight = content["fight"]
        row = next(
            (c for c in fight["characters"] if c["character_name"] == character), None)
        if row is None:
            raise RuntimeError(
                f"fight log entry has no result row for character {character!r}")
        return cls(
            started_at=_normalise(content["cooldown"]["started_at"]),
            result=fight["result"],
            turns=fight["turns"],
            opponent=fight["opponent"],
            logs=tuple(fight["logs"]),
            hp_before=None,
            hp_after=row["final_hp"],
            xp=row["xp"],
            gold=row["gold"],
            drops=tuple(
                FightDrop(code=d["code"], quantity=d["quantity"])
                for d in row["drops"]),
        )
