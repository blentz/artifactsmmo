"""Verify the emergent-specialization epic's three collusion criteria.

The epic's claim is not "characters diverge" (that's covered by role
selection alone) but that they *collude*: one character's production feeds
another's consumption through the shared bank. Three activation criteria
make that concrete, and this script checks all three against real evidence
— the coordination DB and the JSONL trace files a `play --all` session
writes — rather than against unit-test fixtures.

  1. A character held a role — checked against `role_leases` in the
     coordination DB (authoritative), cross-referenced against the trace's
     `role` field (informational: the trace should agree after the fix that
     added `role`/`supply_target` to `_make_cycle_record`'s output, but
     trace files written before that fix legitimately will not).
  2. `SupplyBankGoal` was selected at least once — checked by pattern-matching
     `selected_goal` against `SupplyBankGoal.__repr__`'s exact format,
     `f"SupplyBank({item_code}x{quantity})"` (see
     `artifactsmmo_cli/ai/goals/supply_bank.py`).
  3. A successful `Withdraw` pulled stock a DIFFERENT character deposited —
     the one criterion that proves COLLUSION rather than mere divergence.
     Trace records across every character are merged into one global
     timestamp order, successful `DepositItem(code×qty)` actions are
     recorded per item per depositing character, and a successful
     `Withdraw(code×qty)` by a different character than any prior depositor
     of that code is a hit.

     `DepositAllAction` (`__repr__` -> `"DepositAll"`, no item code) is NOT
     attributable to a specific item and is deliberately excluded from the
     deposit ledger — counting it would require guessing which items it
     moved, which the trace does not record. This under-counts collusion
     evidence rather than over-counting or guessing; see
     `artifactsmmo_cli/ai/actions/deposit_all.py`.

Usage:
    verify_collusion.py <trace-glob> [--db PATH]

`--db` defaults to `learning_db_path.default_learn_db_path()` — the same
default `play`/`multi_run` use — rather than hand-rolling the
`~/.cache/artifactsmmo/learning.db` expression again (five duplicates of it
already exist in this codebase; see `tests/conftest.py`).

Exits 0 when all three criteria pass, 1 otherwise (including when the DB or
trace files can't answer a criterion — an unanswerable criterion is not a
pass).
"""

import argparse
import glob
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session as SqlSession
from sqlmodel import create_engine, select

from artifactsmmo_cli.ai.learning.models import RoleLease
from artifactsmmo_cli.learning_db_path import default_learn_db_path

# `play-trace-{character}-{YYYYMMDD}-{HHMMSS}.jsonl` — the exact format
# `commands/play.py` builds the default trace path with. The character is
# not itself a trace field, so it has to come from the filename.
TRACE_FILENAME_RE = re.compile(r"^play-trace-(?P<character>.+)-\d{8}-\d{6}\.jsonl$")

# `WithdrawItemAction.__repr__` / `DepositItemAction.__repr__` — note the
# multiplication sign is U+00D7 ("×"), not an ASCII "x".
WITHDRAW_RE = re.compile(r"^Withdraw\((?P<code>.+)×(?P<qty>\d+)\)$")
DEPOSIT_ITEM_RE = re.compile(r"^DepositItem\((?P<code>.+)×(?P<qty>\d+)\)$")

# `SupplyBankGoal.__repr__` -> f"SupplyBank({item_code}x{quantity})".
SUPPLY_BANK_GOAL_PREFIX = "SupplyBank("


@dataclass(frozen=True)
class Criterion:
    """One activation criterion's verdict, with the evidence behind it."""

    name: str
    passed: bool
    detail: str


def _character_from_trace_path(path: str) -> str:
    """The character a `play-trace-*.jsonl` file belongs to, from its name.

    Raises on a path that doesn't fit the convention rather than guessing —
    a malformed glob match is a caller error, not evidence to silently drop.
    """
    match = TRACE_FILENAME_RE.match(Path(path).name)
    if match is None:
        raise ValueError(
            f"{path!r} does not match the play-trace filename convention "
            "'play-trace-<character>-<YYYYMMDD>-<HHMMSS>.jsonl' "
            "(see commands/play.py's default trace path)"
        )
    return match.group("character")


def _load_trace_records(trace_glob: str) -> list[dict[str, object]]:
    """Every JSONL record across every file the glob matches, tagged with
    its character (`_character`, from the filename) and merged into one
    global timestamp order — collusion is a cross-character phenomenon, so
    per-file order alone can't show it."""
    records: list[dict[str, object]] = []
    for path in sorted(glob.glob(trace_glob)):
        character = _character_from_trace_path(path)
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record["_character"] = character
                records.append(record)
    records.sort(key=lambda r: str(r["ts"]))
    return records


def _read_role_leases(db_path: str) -> tuple[list[tuple[str, str]], str | None]:
    """`[(role, character), ...]` over every row ever written to
    `role_leases` (expired or not — "held" is a past-tense fact, and an
    expired lease is still proof the coordination mechanism assigned a
    role), plus an honest reason string when the read can't happen at all.

    Deliberately does NOT use `CoordinationStore`: its constructor creates
    the DB directory and the coordination tables as a side effect
    (`SQLModel.metadata.create_all`), which would make a verification
    script that finds nothing indistinguishable from one that silently
    provisioned an empty DB and then found nothing. Checking existence
    first and reading directly keeps this script read-only.
    """
    if not Path(db_path).exists():
        return [], f"no database at {db_path}"
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with SqlSession(engine) as session:
            rows = session.exec(select(RoleLease)).all()
        return [(row.role, row.character) for row in rows], None
    except SQLAlchemyError as exc:
        return [], f"role_leases unreadable in {db_path} ({exc})"
    finally:
        engine.dispose()


def _check_role_held(db_path: str, trace_records: list[dict[str, object]]) -> Criterion:
    rows, db_error = _read_role_leases(db_path)
    trace_roles = {
        str(r["_character"]): r["role"]
        for r in trace_records
        if isinstance(r.get("role"), str)
    }
    if db_error is not None:
        return Criterion(
            "role_held", False,
            f"{db_error}; trace shows a role for: {sorted(trace_roles) or 'nobody'}",
        )
    if not rows:
        return Criterion("role_held", False, f"role_leases is empty in {db_path}")
    held = ", ".join(f"{character}->{role}" for role, character in rows)
    agreeing = sum(1 for role, character in rows if trace_roles.get(character) == role)
    trace_note = (
        f"trace agrees for {agreeing}/{len(rows)}"
        if trace_roles else
        "trace shows no role for any character (pre-fix trace, or role never populated)"
    )
    return Criterion("role_held", True, f"DB: {held}; {trace_note}")


def _check_supply_bank_selected(trace_records: list[dict[str, object]]) -> Criterion:
    goals = ((str(r["_character"]), r.get("selected_goal")) for r in trace_records)
    hits = [
        (character, goal)
        for character, goal in goals
        if isinstance(goal, str) and goal.startswith(SUPPLY_BANK_GOAL_PREFIX)
    ]
    if not hits:
        return Criterion(
            "supply_bank_selected", False,
            f"no {SUPPLY_BANK_GOAL_PREFIX}...) goal in {len(trace_records)} trace record(s)",
        )
    sample = "; ".join(f"{character}: {goal}" for character, goal in hits[:5])
    return Criterion(
        "supply_bank_selected", True,
        f"{len(hits)} cycle(s) selected SupplyBankGoal, e.g. {sample}",
    )


def _check_collusive_withdraw(trace_records: list[dict[str, object]]) -> Criterion:
    deposited_by: dict[str, set[str]] = {}
    withdraw_count = 0
    for record in trace_records:
        if record.get("outcome") != "ok":
            continue
        action = record.get("action")
        if not isinstance(action, str):
            continue
        character = str(record["_character"])
        deposit_match = DEPOSIT_ITEM_RE.match(action)
        if deposit_match:
            deposited_by.setdefault(deposit_match.group("code"), set()).add(character)
            continue
        withdraw_match = WITHDRAW_RE.match(action)
        if withdraw_match:
            withdraw_count += 1
            code = withdraw_match.group("code")
            other_depositors = deposited_by.get(code, set()) - {character}
            if other_depositors:
                return Criterion(
                    "collusive_withdraw", True,
                    f"{character} withdrew {code} previously deposited by "
                    f"{sorted(other_depositors)}",
                )
    if withdraw_count == 0:
        return Criterion(
            "collusive_withdraw", False,
            "no successful Withdraw(...) action in trace",
        )
    return Criterion(
        "collusive_withdraw", False,
        f"{withdraw_count} successful withdraw(s), none matched a DIFFERENT "
        "character's earlier deposit of the same item (DepositAll's "
        "item-level deposits are not attributable and are excluded)",
    )


def run(trace_glob: str, db_path: str) -> list[Criterion]:
    trace_records = _load_trace_records(trace_glob)
    return [
        _check_role_held(db_path, trace_records),
        _check_supply_bank_selected(trace_records),
        _check_collusive_withdraw(trace_records),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the emergent-specialization epic's three "
                     "collusion activation criteria against real trace "
                     "files and the coordination DB.",
    )
    parser.add_argument("trace_glob", help="glob for play-trace-*.jsonl files")
    parser.add_argument(
        "--db", default=None,
        help="coordination DB path (default: the same default learning DB "
             "path play/multi_run use)",
    )
    args = parser.parse_args(argv)

    db_path = args.db if args.db is not None else default_learn_db_path()
    criteria = run(args.trace_glob, db_path)
    for criterion in criteria:
        status = "PASS" if criterion.passed else "FAIL"
        print(f"{status} {criterion.name}: {criterion.detail}")
    return 0 if all(c.passed for c in criteria) else 1


if __name__ == "__main__":
    sys.exit(main())
