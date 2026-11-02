"""No new wall-clock read in decision code (Task 8b, ruling C-3).

Every decision read of "now" in a cycle reads the one cycle clock,
`SelectionContext.now`, stamped once by `GamePlayer._stamp_cycle` (ruling
FR-8). This guard greps `src/artifactsmmo_cli/ai/` for `datetime.now(` and
`time.time(` and fails on any hit outside the allowlist below: the execution
and IO reads (cooldown waits against the server clock, log and trace stamps,
coordination publish and lease times, cache TTLs, display), each with its
reason. A new wall read in decision code fails here, so it is either threaded
from the caller's clock or added below with the reason it is not a decision.

Keyed by (file, enclosing qualified function), not by line, so an edit that
moves a line does not break it; the allowlist is checked both ways, so an entry
whose read was removed fails too."""

import ast
import re
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[2] / "src" / "artifactsmmo_cli" / "ai"
WALL_READ = re.compile(r"datetime\.now\(|time\.time\(")

_COORDINATION = "coordination-store publish/lease/claim times: rows expire on the wall clock the store shares"
_LEARNING_ROW = "learning-store row timestamp (a record of when it happened)"

ALLOWED: dict[tuple[str, str], str] = {
    ("actions/cooldown_wait.py", "wait_out_cooldown"):
        "cooldown wait math against the server's cooldown expiry",
    ("game_data_cache.py", "GameDataCache.read"): "static-data cache TTL",
    ("game_data_cache.py", "GameDataCache.write"): "static-data cache fetched_at stamp",
    ("selection_context.py", "SelectionContext.<lambda>"):
        "stamps a context built OUTSIDE a cycle (offline sweep, audit, test); every "
        "in-cycle context is replaced with the player's `_cycle_now`",
    ("learning/store.py", "LearningStore.start_session"): "session id stamp",
    ("learning/store.py", "LearningStore._ensure_session_row"): _LEARNING_ROW,
    ("learning/store.py", "LearningStore.end_session"): _LEARNING_ROW,
    ("learning/store.py", "LearningStore.set_blocker"): _LEARNING_ROW,
    ("learning/store.py", "LearningStore.record_plan_body"): _LEARNING_ROW,
    ("learning/store.py", "LearningStore.record_decision_events"): _LEARNING_ROW,
    ("learning/store.py", "LearningStore.save_plan_commitment"): _LEARNING_ROW,
    ("learning/store.py", "LearningStore.save_intention"): _LEARNING_ROW,
    ("learning/store.py", "LearningStore.save_refusal_fact"): _LEARNING_ROW,
    ("player.py", "GamePlayer.__init__"):
        "seeds `_cycle_now` before the first `_stamp_cycle`",
    ("player.py", "GamePlayer._stamp_cycle"): "THE cycle clock: read once per cycle",
    ("player.py", "GamePlayer.plan_from_state"): _COORDINATION,
    ("player.py", "GamePlayer.run"):
        "party lease refresh (coordination) and the executed action's cooldown remaining (server clock)",
    ("player.py", "GamePlayer._claim_bank_stock"): _COORDINATION,
    ("player.py", "GamePlayer._claim_ge_order"): _COORDINATION,
    ("player.py", "GamePlayer._fetch_world_state"):
        "sensing: drops events already expired when the world is read; every event "
        "gate re-judges the kept expiries against the cycle clock",
    ("player.py", "GamePlayer._planning_deadline"): "cooldown remaining against the server clock",
    ("player.py", "GamePlayer._wait_for_cooldown"): "cooldown wait against the server clock",
    ("player.py", "GamePlayer._emit_trace"): "trace timestamp and cooldown remaining",
    ("player.py", "GamePlayer._notify_observer"): "TUI snapshot timestamp and cooldown remaining (display)",
    ("player.py", "GamePlayer._pick_supply_target"): _COORDINATION,
    ("player.py", "GamePlayer._refresh_fight_record"):
        "learning-store query window (days of history); read once per cycle",
    ("player.py", "GamePlayer._publish_party_card"): _COORDINATION,
    ("player.py", "GamePlayer._release_led_party"): _COORDINATION,
    ("player.py", "GamePlayer._lead_party"): _COORDINATION,
    ("player.py", "GamePlayer._update_coordination"): _COORDINATION,
    ("player.py", "GamePlayer._resolve_turn_in"): _COORDINATION,
    ("player.py", "GamePlayer._record_learning_cycle"): _LEARNING_ROW,
    ("player.py", "GamePlayer._now"): "console log time (display)",
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
    unexpected = {key: lines for key, lines in wall_reads().items() if key not in ALLOWED}
    assert unexpected == {}, (
        "a wall-clock read in decision code: take the instant from the caller "
        "(`ctx.now`, or a `now` threaded from it), or allowlist it with why it is "
        f"not a decision: {unexpected}")


def test_every_allowlist_entry_still_reads_the_wall() -> None:
    stale = set(ALLOWED) - set(wall_reads())
    assert stale == set(), f"allowlist entries with no wall read left: {sorted(stale)}"

