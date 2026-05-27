"""Mutation runner: each mutant the diff test fails to kill is a survivor -> gate fails."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "artifactsmmo_cli" / "utils" / "pathfinding.py"
TASK_BATCH_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "task_batch.py"

# (description, old, new) -- old strings matched to the actual current pathfinding.py text.
MUTATIONS = [
    # step direction: invert the X step toward target
    ("step-dir: current_x < end_x -> +=1 becomes -=1",
     "        if current_x < end_x:\n            next_x += 1",
     "        if current_x < end_x:\n            next_x -= 1"),
    # step direction: invert the Y step toward target
    ("step-dir: current_y < end_y -> +=1 becomes -=1",
     "        if current_y < end_y:\n            next_y += 1",
     "        if current_y < end_y:\n            next_y -= 1"),
    # loop condition: or -> and (stops early on either axis aligned)
    ("loop-cond: while ... or ... -> and",
     "    while current_x != end_x or current_y != end_y:",
     "    while current_x != end_x and current_y != end_y:"),
    # total_distance: subtraction instead of addition of the two axis deltas
    ("total_distance: + -> - between axis deltas",
     "    total_distance = abs(end_x - start_x) + abs(end_y - start_y)",
     "    total_distance = abs(end_x - start_x) - abs(end_y - start_y)"),
    # total_distance: drop the Y term entirely
    ("total_distance: drop abs(end_y - start_y) term",
     "    total_distance = abs(end_x - start_x) + abs(end_y - start_y)",
     "    total_distance = abs(end_x - start_x)"),
    # estimated_time: change the per-step factor 5 -> 6
    ("estimated_time factor",
     "estimated_time = len(steps) * 5",
     "estimated_time = len(steps) * 6"),
]


# task_batch mutations -- old strings matched to the actual current task_batch.py text.
TASK_BATCH_MUTATIONS = [
    # invert the max(1, ...) floor: drop the floor so a 0-fit case yields 0, not 1.
    ("task_batch: drop max(1, ...) floor",
     "    return max(1, min(remaining, fit, BATCH_CAP))",
     "    return min(remaining, fit, BATCH_CAP)"),
    # drop the BATCH_CAP clamp entirely (allows results > 10).
    ("task_batch: drop BATCH_CAP clamp",
     "    return max(1, min(remaining, fit, BATCH_CAP))",
     "    return max(1, min(remaining, fit))"),
    # off-by-one on remaining (use task_total instead of task_total - progress).
    ("task_batch: off-by-one remaining (+1)",
     "    remaining = state.task_total - state.task_progress",
     "    remaining = state.task_total - state.task_progress + 1"),
]


def run_diff(test_path: str) -> int:
    return subprocess.run(
        ["uv", "run", "pytest", test_path, "-q", "--no-cov", "-x"],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    ).returncode


def run_group(src: Path, mutations, test_path: str, survivors: list) -> None:
    orig = src.read_text()
    try:
        for desc, old, new in mutations:
            if old not in orig:
                print(f"STALE MUTATION (text not found): {desc}")
                survivors.append(desc + " (stale)")
                continue
            src.write_text(orig.replace(old, new, 1))
            if run_diff(test_path) == 0:
                print(f"SURVIVED: {desc}")
                survivors.append(desc)
            else:
                print(f"killed: {desc}")
    finally:
        src.write_text(orig)


def main() -> int:
    survivors: list = []
    run_group(SRC, MUTATIONS, "formal/diff/test_calculate_path_diff.py", survivors)
    run_group(TASK_BATCH_SRC, TASK_BATCH_MUTATIONS, "formal/diff/test_task_batch_diff.py", survivors)
    if survivors:
        print(f"GATE FAIL: survivors={survivors}")
        return 1
    print("mutation gate OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
