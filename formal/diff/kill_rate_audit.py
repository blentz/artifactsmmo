"""Item 12: per-file mutation kill-rate audit.

Statically parses `formal/diff/mutate.py` to enumerate every
`run_group(SRC, MUTATIONS, test_path, survivors)` call and produce:

  • formal/diff/kill_rate_report.txt — per-(SRC, test) row with the
    mutation count.
  • Per-source-file aggregation: total mutations covered, distinct
    test files.

Goal (12b): 100% kill rate measured by an actual mutate.py run; this
tool enumerates the surface area. Combine with a saved survivors list
(written by mutate.py) for the kill-rate dashboard.

Run from the repo root:
    uv run python formal/diff/kill_rate_audit.py
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MUTATE_PY = REPO_ROOT / "formal" / "diff" / "mutate.py"
REPORT = REPO_ROOT / "formal" / "diff" / "kill_rate_report.txt"


def parse_run_group_calls(path: Path) -> list[tuple[str, str, str]]:
    """Return [(src_const, mutations_const, test_path), ...] from
    `run_group(SRC, MUTATIONS, "...test_path...", survivors)` calls."""
    tree = ast.parse(path.read_text())
    calls: list[tuple[str, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "run_group":
            continue
        if len(node.args) < 3:
            continue
        src_arg, mut_arg, test_arg = node.args[0], node.args[1], node.args[2]
        src = src_arg.id if isinstance(src_arg, ast.Name) else "<expr>"
        mut = mut_arg.id if isinstance(mut_arg, ast.Name) else "<expr>"
        if isinstance(test_arg, ast.Constant) and isinstance(test_arg.value, str):
            test = test_arg.value
        else:
            test = "<expr>"
        calls.append((src, mut, test))
    return calls


def count_mutations_per_constant(path: Path) -> dict[str, int]:
    """Return {MUTATIONS_NAME: count} by reading each top-level list/tuple
    assignment. A mutation is one ELEMENT of the list."""
    tree = ast.parse(path.read_text())
    counts: dict[str, int] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if not name.endswith("MUTATIONS"):
            continue
        val = node.value
        if isinstance(val, (ast.List, ast.Tuple)):
            counts[name] = len(val.elts)
        else:
            counts[name] = -1  # not a literal — skip
    return counts


def report(calls: list[tuple[str, str, str]], mut_counts: dict[str, int]) -> str:
    lines: list[str] = []
    lines.append("# Item 12 — Mutation kill-rate audit (enumeration surface)\n")
    lines.append(f"Source of truth: formal/diff/mutate.py")
    lines.append(f"Total run_group calls: {len(calls)}")
    src_to_calls: dict[str, list[tuple[str, str]]] = defaultdict(list)
    test_to_calls: dict[str, list[tuple[str, str]]] = defaultdict(list)
    total_mutations = 0
    for src, mut, test in calls:
        n = mut_counts.get(mut, -1)
        src_to_calls[src].append((mut, test))
        test_to_calls[test].append((src, mut))
        if n >= 0:
            total_mutations += n
    lines.append(f"Total enumerated mutations: {total_mutations}\n")

    lines.append("## Per-source-constant breakdown\n")
    for src in sorted(src_to_calls):
        entries = src_to_calls[src]
        total = sum(mut_counts.get(m, 0) for m, _ in entries)
        lines.append(f"  {src} — {total} mutations across {len(entries)} test(s)")
        for mut, test in entries:
            n = mut_counts.get(mut, -1)
            lines.append(f"    {mut} ({n}) → {test}")

    lines.append("\n## Per-test-file aggregation\n")
    for test in sorted(test_to_calls):
        entries = test_to_calls[test]
        total = sum(mut_counts.get(m, 0) for _, m in entries)
        lines.append(f"  {test} — {total} mutations across {len(entries)} src(s)")

    return "\n".join(lines) + "\n"


def main() -> None:
    calls = parse_run_group_calls(MUTATE_PY)
    mut_counts = count_mutations_per_constant(MUTATE_PY)
    text = report(calls, mut_counts)
    REPORT.write_text(text)
    print(text[:3000])
    print(f"\n(full report at {REPORT.relative_to(REPO_ROOT)})")


if __name__ == "__main__":
    main()
