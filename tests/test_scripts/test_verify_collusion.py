"""Tests for scripts/verify_collusion.py — the emergent-specialization
epic's activation-criteria checker.

It is a script, but it encodes the epic's definition of success, so it gets
the same test treatment as any other module: every branch, both real
degrade paths (missing DB, missing tables), and the exit-code contract.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from sqlmodel import Session as SqlSession
from sqlmodel import SQLModel, create_engine

from artifactsmmo_cli.ai.learning.models import RoleLease
from scripts import verify_collusion as vc

SCRIPT_PATH = Path(vc.__file__)


def _write_trace(path: Path, character: str, ts_suffix: str, records: list[dict]) -> Path:
    """Write `records` as a play-trace-<character>-<ts>.jsonl file."""
    trace_path = path / f"play-trace-{character}-{ts_suffix}.jsonl"
    with open(trace_path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    return trace_path


def _record(ts: str, **overrides: object) -> dict:
    base = {
        "ts": ts,
        "cycle": 0,
        "selected_goal": "RestoreHP",
        "action": "Rest()",
        "outcome": "ok",
        "role": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _character_from_trace_path
# ---------------------------------------------------------------------------

def test_character_from_trace_path_parses_the_convention():
    assert vc._character_from_trace_path(
        "play-trace-R2D2-20260802-111756.jsonl"
    ) == "R2D2"


def test_character_from_trace_path_rejects_a_non_conforming_name():
    with pytest.raises(ValueError, match="does not match the play-trace"):
        vc._character_from_trace_path("not-a-trace-file.jsonl")


# ---------------------------------------------------------------------------
# _load_trace_records
# ---------------------------------------------------------------------------

def test_load_trace_records_merges_files_into_one_timestamp_order(tmp_path: Path):
    _write_trace(tmp_path, "Robby", "20260802-000000", [
        _record("2026-08-02T00:00:02+00:00", cycle=1),
    ])
    _write_trace(tmp_path, "HAL", "20260802-000000", [
        _record("2026-08-02T00:00:01+00:00", cycle=0),
    ])

    records = vc._load_trace_records(str(tmp_path / "play-trace-*.jsonl"))

    assert [r["_character"] for r in records] == ["HAL", "Robby"]


def test_load_trace_records_skips_blank_lines(tmp_path: Path):
    trace_path = tmp_path / "play-trace-Robby-20260802-000000.jsonl"
    with open(trace_path, "w", encoding="utf-8") as handle:
        handle.write("\n")
        handle.write(json.dumps(_record("2026-08-02T00:00:00+00:00")) + "\n")
        handle.write("   \n")

    records = vc._load_trace_records(str(tmp_path / "play-trace-*.jsonl"))

    assert len(records) == 1


def test_load_trace_records_empty_glob_yields_no_records(tmp_path: Path):
    assert vc._load_trace_records(str(tmp_path / "play-trace-*.jsonl")) == []


# ---------------------------------------------------------------------------
# _read_role_leases
# ---------------------------------------------------------------------------

def test_read_role_leases_reports_a_missing_database(tmp_path: Path):
    rows, error = vc._read_role_leases(str(tmp_path / "nope.db"))

    assert rows == []
    assert error is not None
    assert "no database" in error


def test_read_role_leases_reports_a_database_with_no_coordination_tables(tmp_path: Path):
    """A real sqlite file that predates the coordination tables (or never
    had them) must degrade honestly, not crash."""
    db_path = tmp_path / "bare.db"
    Path(db_path).touch()

    rows, error = vc._read_role_leases(str(db_path))

    assert rows == []
    assert error is not None
    assert "unreadable" in error


def test_read_role_leases_returns_every_row(tmp_path: Path):
    db_path = tmp_path / "coord.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with SqlSession(engine) as session:
        session.add(RoleLease(role="miner", character="Robby",
                              claimed_at="2026-08-02T00:00:00+00:00",
                              expires_at="2026-08-02T00:10:00+00:00"))
        session.add(RoleLease(role="logger", character="R2D2",
                              claimed_at="2026-08-02T00:00:00+00:00",
                              expires_at="2026-08-02T00:10:00+00:00"))
        session.commit()
    engine.dispose()

    rows, error = vc._read_role_leases(str(db_path))

    assert error is None
    assert sorted(rows) == [("logger", "R2D2"), ("miner", "Robby")]


# ---------------------------------------------------------------------------
# _check_role_held
# ---------------------------------------------------------------------------

def test_check_role_held_fails_on_missing_db(tmp_path: Path):
    criterion = vc._check_role_held(str(tmp_path / "nope.db"), [])

    assert criterion.passed is False
    assert "no database" in criterion.detail


def test_check_role_held_ignores_a_null_role_field_in_trace(tmp_path: Path):
    """A cycle with no role held still emits a `role` key (Job 1: present
    but null, not omitted) — that null must NOT be read as 'this character
    has a role', or a coordination-idle character would misreport as
    holding one."""
    criterion = vc._check_role_held(
        str(tmp_path / "nope.db"), [{"_character": "Robby", "role": None}],
    )

    assert criterion.passed is False
    assert "trace shows a role for: nobody" in criterion.detail


def test_check_role_held_fails_on_empty_role_leases(tmp_path: Path):
    db_path = tmp_path / "coord.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    engine.dispose()

    criterion = vc._check_role_held(str(db_path), [])

    assert criterion.passed is False
    assert "empty" in criterion.detail


def test_check_role_held_passes_and_notes_trace_disagreement(tmp_path: Path):
    """A pre-fix trace file legitimately carries no `role` field — the
    criterion still passes (the DB is authoritative) but says so."""
    db_path = tmp_path / "coord.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with SqlSession(engine) as session:
        session.add(RoleLease(role="miner", character="Robby",
                              claimed_at="2026-08-02T00:00:00+00:00",
                              expires_at="2026-08-02T00:10:00+00:00"))
        session.commit()
    engine.dispose()

    criterion = vc._check_role_held(str(db_path), [])

    assert criterion.passed is True
    assert "Robby->miner" in criterion.detail
    assert "no role for any character" in criterion.detail


def test_check_role_held_passes_and_notes_trace_agreement(tmp_path: Path):
    db_path = tmp_path / "coord.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with SqlSession(engine) as session:
        session.add(RoleLease(role="miner", character="Robby",
                              claimed_at="2026-08-02T00:00:00+00:00",
                              expires_at="2026-08-02T00:10:00+00:00"))
        session.commit()
    engine.dispose()
    trace_records = [{"_character": "Robby", "role": "miner"}]

    criterion = vc._check_role_held(str(db_path), trace_records)

    assert criterion.passed is True
    assert "trace agrees for 1/1" in criterion.detail


# ---------------------------------------------------------------------------
# _check_supply_bank_selected
# ---------------------------------------------------------------------------

def test_check_supply_bank_selected_fails_when_never_selected():
    trace_records = [
        {"_character": "Robby", "selected_goal": "RestoreHP"},
        {"_character": "HAL", "selected_goal": "GatherMaterials(iron_ore, {iron_ore:10})"},
    ]

    criterion = vc._check_supply_bank_selected(trace_records)

    assert criterion.passed is False
    assert "no SupplyBank(" in criterion.detail


def test_check_supply_bank_selected_passes_on_a_match():
    trace_records = [
        {"_character": "Robby", "selected_goal": "SupplyBank(iron_ore x10)"},
    ]

    criterion = vc._check_supply_bank_selected(trace_records)

    assert criterion.passed is True
    assert "1 cycle" in criterion.detail
    assert "Robby: SupplyBank(iron_ore x10)" in criterion.detail


def test_check_supply_bank_selected_ignores_non_string_goals():
    """`selected_goal` is `<none>` on a no-plan cycle, but the field type is
    always a string in practice — guard against a record with a missing or
    null goal, which must not raise."""
    trace_records = [{"_character": "Robby", "selected_goal": None}]

    criterion = vc._check_supply_bank_selected(trace_records)

    assert criterion.passed is False


# ---------------------------------------------------------------------------
# _check_collusive_withdraw
# ---------------------------------------------------------------------------

def test_check_collusive_withdraw_fails_with_no_withdraws():
    trace_records = [
        {"_character": "Robby", "outcome": "ok", "action": "GatherAction(iron_ore)"},
    ]

    criterion = vc._check_collusive_withdraw(trace_records)

    assert criterion.passed is False
    assert "no successful Withdraw" in criterion.detail


def test_check_collusive_withdraw_fails_on_self_withdraw_only():
    trace_records = [
        {"_character": "Robby", "outcome": "ok", "action": "DepositItem(iron_ore×10)"},
        {"_character": "Robby", "outcome": "ok", "action": "Withdraw(iron_ore×5)"},
    ]

    criterion = vc._check_collusive_withdraw(trace_records)

    assert criterion.passed is False
    assert "1 successful withdraw" in criterion.detail


def test_check_collusive_withdraw_passes_on_a_cross_character_pair():
    trace_records = [
        {"_character": "Robby", "outcome": "ok", "action": "DepositItem(iron_ore×10)"},
        {"_character": "R2D2", "outcome": "ok", "action": "Withdraw(iron_ore×5)"},
    ]

    criterion = vc._check_collusive_withdraw(trace_records)

    assert criterion.passed is True
    assert "R2D2 withdrew iron_ore" in criterion.detail
    assert "Robby" in criterion.detail


def test_check_collusive_withdraw_ignores_a_failed_deposit():
    """A deposit that errored never landed in the bank — it must not count
    as evidence a sibling can withdraw from."""
    trace_records = [
        {"_character": "Robby", "outcome": "error:other", "action": "DepositItem(iron_ore×10)"},
        {"_character": "R2D2", "outcome": "ok", "action": "Withdraw(iron_ore×5)"},
    ]

    criterion = vc._check_collusive_withdraw(trace_records)

    assert criterion.passed is False


def test_check_collusive_withdraw_ignores_a_failed_withdraw():
    trace_records = [
        {"_character": "Robby", "outcome": "ok", "action": "DepositItem(iron_ore×10)"},
        {"_character": "R2D2", "outcome": "error:other", "action": "Withdraw(iron_ore×5)"},
    ]

    criterion = vc._check_collusive_withdraw(trace_records)

    assert criterion.passed is False
    assert "no successful Withdraw" in criterion.detail


def test_check_collusive_withdraw_ignores_deposit_all_and_missing_action():
    """`DepositAll` carries no item code, so it cannot seed the ledger; a
    record with no `action` key at all (defensive) must not raise."""
    trace_records = [
        {"_character": "Robby", "outcome": "ok", "action": "DepositAll"},
        {"_character": "R2D2", "outcome": "ok"},
        {"_character": "R2D2", "outcome": "ok", "action": "Withdraw(iron_ore×5)"},
    ]

    criterion = vc._check_collusive_withdraw(trace_records)

    assert criterion.passed is False
    assert "1 successful withdraw" in criterion.detail


# ---------------------------------------------------------------------------
# run / main — end to end
# ---------------------------------------------------------------------------

def _seed_db(db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with SqlSession(engine) as session:
        session.add(RoleLease(role="miner", character="Robby",
                              claimed_at="2026-08-02T00:00:00+00:00",
                              expires_at="2026-08-02T00:10:00+00:00"))
        session.commit()
    engine.dispose()


def test_run_returns_all_three_criteria_in_order(tmp_path: Path):
    _seed_db(tmp_path / "coord.db")
    _write_trace(tmp_path, "Robby", "20260802-000000", [
        _record("2026-08-02T00:00:00+00:00",
                selected_goal="SupplyBank(iron_ore x10)",
                action="DepositItem(iron_ore×10)"),
    ])
    _write_trace(tmp_path, "R2D2", "20260802-000001", [
        _record("2026-08-02T00:00:01+00:00", action="Withdraw(iron_ore×5)"),
    ])

    criteria = vc.run(str(tmp_path / "play-trace-*.jsonl"), str(tmp_path / "coord.db"))

    assert [c.name for c in criteria] == [
        "role_held", "supply_bank_selected", "collusive_withdraw",
    ]
    assert all(c.passed for c in criteria)


def test_main_exits_zero_when_all_criteria_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    _seed_db(tmp_path / "coord.db")
    _write_trace(tmp_path, "Robby", "20260802-000000", [
        _record("2026-08-02T00:00:00+00:00",
                selected_goal="SupplyBank(iron_ore x10)",
                action="DepositItem(iron_ore×10)"),
    ])
    _write_trace(tmp_path, "R2D2", "20260802-000001", [
        _record("2026-08-02T00:00:01+00:00", action="Withdraw(iron_ore×5)"),
    ])

    rc = vc.main([
        str(tmp_path / "play-trace-*.jsonl"),
        "--db", str(tmp_path / "coord.db"),
    ])

    assert rc == 0
    out = capsys.readouterr().out
    assert "PASS role_held" in out
    assert "PASS supply_bank_selected" in out
    assert "PASS collusive_withdraw" in out


def test_main_exits_one_when_any_criterion_fails(tmp_path: Path):
    rc = vc.main([
        str(tmp_path / "play-trace-*.jsonl"),
        "--db", str(tmp_path / "nope.db"),
    ])

    assert rc == 1


def test_script_runs_as_a_subprocess_and_exits_one_on_no_evidence(tmp_path: Path):
    """Exercises the real `if __name__ == "__main__":` entry point, not just
    `main()` called in-process — `--db` is passed explicitly so this never
    touches the real default learning DB path."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH),
         str(tmp_path / "play-trace-*.jsonl"),
         "--db", str(tmp_path / "nope.db")],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 1
    assert "FAIL role_held" in result.stdout


def test_main_defaults_db_to_default_learn_db_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """`--db` is optional; omitting it must fall through to
    `default_learn_db_path()`, not a hand-rolled duplicate."""
    sentinel = str(tmp_path / "sentinel.db")
    monkeypatch.setattr(vc, "default_learn_db_path", lambda: sentinel)

    rc = vc.main([str(tmp_path / "play-trace-*.jsonl")])

    assert rc == 1
    rows, error = vc._read_role_leases(sentinel)
    assert rows == []
    assert error == f"no database at {sentinel}"
