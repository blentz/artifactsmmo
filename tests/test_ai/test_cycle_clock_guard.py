"""No new wall-clock read in decision code (Task 8b, ruling C-3).

Every decision read of "now" in a cycle reads the one cycle clock,
`SelectionContext.now`, stamped once by `GamePlayer._stamp_cycle` (ruling
FR-8). This guard greps `src/artifactsmmo_cli/ai/` for `datetime.now(` and
`time.time(` and fails on any hit outside the allowlist below: the execution
and IO reads (cooldown waits against the server clock, log and trace stamps,
coordination publish and lease times, cache TTLs, display), each with its
reason. A new wall read in decision code fails here, so it is either threaded
from the caller's clock or added below with the reason it is not a decision.

Keyed by (file, enclosing qualified function) with the number of reads that
scope holds, not by line, so an edit that moves a line does not break it while a
new read inside an allowlisted function does. The allowlist is checked both
ways, so an entry whose read was removed fails too, and a clock imported under
another name fails on its own."""

import ast
import re
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[2] / "src" / "artifactsmmo_cli" / "ai"
WALL_READ = re.compile(r"\b(datetime|date)\.(now|utcnow|today)\b|\btime\.time\b")
"""A wall read, called or passed as a callable (`default_factory=datetime.now`,
`clock=time.time`)."""

ALIASED_CLOCK = re.compile(
    r"^\s*(import\s+(datetime|time)\s+as\s|from\s+time\s+import\b|"
    r"from\s+datetime\s+import\s.*\b(datetime|date)\s+as\s)", re.M)
"""An import that would let a wall read escape `WALL_READ` under another name."""

_COORDINATION = "coordination-store publish/lease/claim times: rows expire on the wall clock the store shares"
_COORDINATION_DECISION = ("coordination TTL feeding the {}: the sibling rows are stamped on the "
                          "wall by other processes, so their TTL is judged on that same wall")
_LEARNING_ROW = "learning-store row timestamp (a record of when it happened)"

ALLOWED: dict[tuple[str, str], tuple[int, str]] = {
    ("account_read_cache.py", "AccountReadCache.__init__"): (1, "account-read cache TTL clock"),
    ("actions/cooldown_wait.py", "wait_out_cooldown"):
        (1, "cooldown wait math against the server's cooldown expiry"),
    ("game_data_cache.py", "GameDataCache.read"): (1, "static-data cache TTL"),
    ("game_data_cache.py", "GameDataCache.write"): (1, "static-data cache fetched_at stamp"),
    ("selection_context.py", "SelectionContext.<lambda>"):
        (1, "stamps a context built OUTSIDE a cycle (offline sweep, audit, test); every "
            "in-cycle context is replaced with the player's `_cycle_now`"),
    ("learning/store.py", "LearningStore.start_session"): (1, "session id stamp"),
    ("learning/store.py", "LearningStore._ensure_session_row"): (1, _LEARNING_ROW),
    ("learning/store.py", "LearningStore.end_session"): (1, _LEARNING_ROW),
    ("learning/store.py", "LearningStore.set_blocker"): (2, _LEARNING_ROW),
    ("learning/store.py", "LearningStore.record_plan_body"): (1, _LEARNING_ROW),
    ("learning/store.py", "LearningStore.record_decision_events"): (1, _LEARNING_ROW),
    ("learning/store.py", "LearningStore.save_plan_commitment"): (1, _LEARNING_ROW),
    ("learning/store.py", "LearningStore.save_intention"): (2, _LEARNING_ROW),
    ("learning/store.py", "LearningStore.save_refusal_fact"): (1, _LEARNING_ROW),
    ("player.py", "GamePlayer.__init__"): (1, "seeds `_cycle_now` before the first `_stamp_cycle`"),
    ("player.py", "GamePlayer._stamp_cycle"): (1, "THE cycle clock: read once per cycle"),
    ("player.py", "GamePlayer.plan_from_state"): (3, _COORDINATION),
    ("player.py", "GamePlayer.run"):
        (2, "party lease refresh (coordination) and the executed action's cooldown "
            "remaining (server clock)"),
    ("player.py", "GamePlayer._claim_bank_stock"): (1, _COORDINATION),
    ("player.py", "GamePlayer._claim_ge_order"): (1, _COORDINATION),
    ("player.py", "GamePlayer._fetch_world_state"):
        (1, "sensing: drops events already expired when the world is read; every event "
            "gate re-judges the kept expiries against the cycle clock"),
    ("player.py", "GamePlayer._planning_deadline"): (1, "cooldown remaining against the server clock"),
    ("player.py", "GamePlayer._wait_for_cooldown"): (1, "cooldown wait against the server clock"),
    ("player.py", "GamePlayer._emit_trace"): (2, "trace timestamp and cooldown remaining"),
    ("player.py", "GamePlayer._notify_observer"):
        (2, "TUI snapshot timestamp and cooldown remaining (display)"),
    ("player.py", "GamePlayer._pick_supply_target"):
        (1, _COORDINATION_DECISION.format("supply-target decision")),
    ("player.py", "GamePlayer._refresh_fight_record"):
        (1, "learning-store query window (days of history); read once per cycle"),
    ("player.py", "GamePlayer._publish_party_card"): (1, _COORDINATION),
    ("player.py", "GamePlayer._release_led_party"): (1, _COORDINATION),
    ("player.py", "GamePlayer._lead_party"): (1, _COORDINATION),
    ("player.py", "GamePlayer._update_coordination"): (1, _COORDINATION),
    ("player.py", "GamePlayer._resolve_turn_in"):
        (1, _COORDINATION_DECISION.format("turn-in decision")),
    ("player.py", "GamePlayer._record_learning_cycle"): (1, _LEARNING_ROW),
    ("player.py", "GamePlayer._now"): (1, "console log time (display)"),
}


def _spans(tree: ast.Module) -> list[tuple[int, int, str]]:
    """(first line, last line, qualified name) of every def, class and lambda."""
    spans: list[tuple[int, int, str]] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda):
                name = "<lambda>" if isinstance(child, ast.Lambda) else child.name
                qualified = f"{prefix}.{name}" if prefix else name
                spans.append((child.lineno, child.end_lineno or child.lineno, qualified))
                visit(child, qualified)
            else:
                visit(child, prefix)

    visit(tree, "")
    return spans


def wall_reads() -> dict[tuple[str, str], list[int]]:
    """Every wall-clock read under `ai/`, by (file, innermost enclosing scope)."""
    hits: dict[tuple[str, str], list[int]] = {}
    for path in sorted(AI_ROOT.rglob("*.py")):
        source = path.read_text()
        if not WALL_READ.search(source):
            continue
        spans = _spans(ast.parse(source))
        for number, line in enumerate(source.splitlines(), 1):
            if not WALL_READ.search(line):
                continue
            enclosing = [span for span in spans if span[0] <= number <= span[1]]
            scope = max(enclosing, key=lambda span: span[0])[2] if enclosing else "<module>"
            hits.setdefault((path.relative_to(AI_ROOT).as_posix(), scope), []).append(number)
    return hits


def test_every_wall_read_in_ai_is_an_allowlisted_execution_or_io_read() -> None:
    """Each allowlisted scope holds exactly its counted reads: a new one, even
    inside an allowlisted function, fails here."""
    unexpected = {key: lines for key, lines in wall_reads().items()
                  if key not in ALLOWED or len(lines) != ALLOWED[key][0]}
    assert unexpected == {}, (
        "a wall-clock read in decision code: take the instant from the caller "
        "(`ctx.now`, or a `now` threaded from it), or allowlist it with why it is "
        f"not a decision (and its count): {unexpected}")


def test_every_allowlist_entry_still_reads_the_wall() -> None:
    stale = set(ALLOWED) - set(wall_reads())
    assert stale == set(), f"allowlist entries with no wall read left: {sorted(stale)}"


def test_no_clock_is_imported_under_another_name() -> None:
    aliased = [path.relative_to(AI_ROOT).as_posix() for path in sorted(AI_ROOT.rglob("*.py"))
               if ALIASED_CLOCK.search(path.read_text())]
    assert aliased == [], f"a clock import WALL_READ cannot see: {aliased}"


def test_the_guard_sees_every_spelling_of_a_wall_read() -> None:
    """Non-vacuity of the regexes against the spellings a decision could use."""
    for spelling in ("datetime.now(UTC)", "datetime.utcnow()", "date.today()",
                     "field(default_factory=datetime.now)", "clock=time.time", "time.time()"):
        assert WALL_READ.search(spelling), spelling
    assert not WALL_READ.search("ctx.now")
    for spelling in ("import datetime as dt", "from time import time",
                     "from datetime import datetime as Clock"):
        assert ALIASED_CLOCK.search(spelling), spelling
