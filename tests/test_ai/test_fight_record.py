"""FightRecord construction from both API shapes."""

import datetime
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from artifactsmmo_cli.ai.fight_record import FightDrop, FightRecord

STARTED_AT = "2026-07-27T23:30:30.455000"

LOGS = [
    "Fight start: Robby HP: 485/485 vs Mushmush HP: 350/350",
    "Turn 1: Robby used fire attack and dealt 12 damage. Mushmush HP: 338/350",
]


def make_row(name, xp=45, gold=12, final_hp=275, drops=()):
    row = MagicMock()
    row.character_name = name
    row.xp = xp
    row.gold = gold
    row.final_hp = final_hp
    row.drops = [MagicMock(code=c, quantity=q) for c, q in drops]
    return row


def make_response(rows, result="win", turns=27, opponent="mushmush"):
    data = MagicMock()
    data.cooldown.started_at = datetime.datetime.fromisoformat(STARTED_AT)
    data.fight.result.value = result
    data.fight.turns = turns
    data.fight.opponent = opponent
    data.fight.logs = list(LOGS)
    data.fight.characters = rows
    return data


def make_content(rows, result="win", turns=27, opponent="mushmush"):
    return {
        "cooldown": {"started_at": STARTED_AT},
        "fight": {
            "result": result,
            "turns": turns,
            "opponent": opponent,
            "logs": list(LOGS),
            "characters": rows,
        },
    }


def content_row(name, xp=45, gold=12, final_hp=275, drops=()):
    return {
        "character_name": name,
        "xp": xp,
        "gold": gold,
        "final_hp": final_hp,
        "drops": [{"code": c, "quantity": q} for c, q in drops],
    }


class TestFromFightResponse:
    def test_reads_structured_fields(self):
        data = make_response([make_row("Robby", drops=(("mushmush_hat", 1),))])

        rec = FightRecord.from_fight_response(data, character="Robby", hp_before=485)

        assert rec.result == "win"
        assert rec.turns == 27
        assert rec.opponent == "mushmush"
        assert rec.logs == tuple(LOGS)
        assert rec.hp_before == 485
        assert rec.hp_after == 275
        assert rec.xp == 45
        assert rec.gold == 12
        assert rec.drops == (FightDrop(code="mushmush_hat", quantity=1),)

    def test_selects_participant_by_name_not_index(self):
        rows = [make_row("Wakko", final_hp=10), make_row("Robby", final_hp=275)]

        rec = FightRecord.from_fight_response(
            make_response(rows), character="Robby", hp_before=485)

        assert rec.hp_after == 275

    def test_raises_when_character_absent(self):
        data = make_response([make_row("Wakko")])

        with pytest.raises(RuntimeError, match="Robby"):
            FightRecord.from_fight_response(data, character="Robby", hp_before=485)

    def test_loss_result(self):
        data = make_response([make_row("Robby", final_hp=0)], result="loss", turns=41)

        rec = FightRecord.from_fight_response(data, character="Robby", hp_before=320)

        assert rec.result == "loss"
        assert rec.hp_after == 0


class TestFromLogEntry:
    def test_reads_structured_fields(self):
        content = make_content([content_row("Robby", drops=(("mushmush_hat", 1),))])

        rec = FightRecord.from_log_entry(content, character="Robby")

        assert rec.result == "win"
        assert rec.turns == 27
        assert rec.logs == tuple(LOGS)
        assert rec.hp_after == 275
        assert rec.drops == (FightDrop(code="mushmush_hat", quantity=1),)

    def test_hp_before_is_none_because_the_log_never_carries_it(self):
        content = make_content([content_row("Robby")])

        rec = FightRecord.from_log_entry(content, character="Robby")

        assert rec.hp_before is None

    def test_selects_participant_by_name_not_index(self):
        content = make_content([content_row("Wakko", final_hp=10),
                                content_row("Robby", final_hp=275)])

        rec = FightRecord.from_log_entry(content, character="Robby")

        assert rec.hp_after == 275

    def test_raises_when_character_absent(self):
        content = make_content([content_row("Wakko")])

        with pytest.raises(RuntimeError, match="Robby"):
            FightRecord.from_log_entry(content, character="Robby")


class TestIdentity:
    def test_started_at_is_identical_across_both_shapes(self):
        """The dedup key for merging session and backfilled fights."""
        live = FightRecord.from_fight_response(
            make_response([make_row("Robby")]), character="Robby", hp_before=485)
        backfilled = FightRecord.from_log_entry(
            make_content([content_row("Robby")]), character="Robby")

        assert live.started_at == backfilled.started_at

    def test_started_at_normalises_a_zulu_suffix(self):
        content = make_content([content_row("Robby")])
        content["cooldown"]["started_at"] = "2026-07-27T23:30:30.455000Z"
        live = FightRecord.from_fight_response(
            make_response([make_row("Robby")]), character="Robby", hp_before=485)

        backfilled = FightRecord.from_log_entry(content, character="Robby")

        assert backfilled.started_at.startswith("2026-07-27T23:30:30.455000")
        assert live.started_at.startswith("2026-07-27T23:30:30.455000")

    def test_record_is_frozen(self):
        rec = FightRecord.from_fight_response(
            make_response([make_row("Robby")]), character="Robby", hp_before=485)

        with pytest.raises(ValidationError):
            rec.turns = 5
