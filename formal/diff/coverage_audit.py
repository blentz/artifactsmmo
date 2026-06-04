"""Item 9: Differential-coverage audit.

Enumerates every top-level function in `src/artifactsmmo_cli/ai/` and
maps it to the diff test that exercises it (best-effort name match
against `formal/diff/test_*_diff.py`). Reports the coverage gap.

Run from the repo root:
    uv run python formal/diff/coverage_audit.py

Outputs:
    formal/diff/coverage_audit_report.txt

Honest disclosure: function→test matching is by name heuristic (filename
prefix). A function in `bank_selection.py` is "covered" if
`test_bank_selection_diff.py` exists. Line/branch coverage is the
mutation-kill rate from Item 10/12. Item 9's deliverable is the
function-level enumeration + gap list.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AI_SRC = REPO_ROOT / "src" / "artifactsmmo_cli" / "ai"
DIFF_TESTS = REPO_ROOT / "formal" / "diff"
REPORT = DIFF_TESTS / "coverage_audit_report.txt"


def enumerate_functions(src: Path) -> dict[str, list[str]]:
    """Return {module_path: [function_name, ...]} for every .py under src."""
    result: dict[str, list[str]] = {}
    for path in sorted(src.rglob("*.py")):
        if path.name.startswith("_") and path.name != "__init__.py":
            continue
        rel = path.relative_to(src).as_posix()
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        funcs: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.append(node.name)
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        funcs.append(f"{node.name}.{item.name}")
        if funcs:
            result[rel] = funcs
    return result


def diff_test_modules(diff_dir: Path) -> set[str]:
    """Return {'bank_selection', 'cycle_step', ...} from test_<name>_diff.py."""
    out: set[str] = set()
    for path in diff_dir.glob("test_*_diff.py"):
        stem = path.stem  # test_bank_selection_diff
        if stem.startswith("test_") and stem.endswith("_diff"):
            out.add(stem[len("test_"):-len("_diff")])
    return out


def report(funcs: dict[str, list[str]], tests: set[str]) -> str:
    lines: list[str] = []
    lines.append("# Item 9 — Differential coverage audit\n")
    lines.append(f"Source root: src/artifactsmmo_cli/ai/")
    lines.append(f"Diff tests: formal/diff/test_*_diff.py")
    lines.append(f"Modules with functions: {len(funcs)}")
    total_funcs = sum(len(v) for v in funcs.values())
    lines.append(f"Total functions: {total_funcs}")
    lines.append(f"Existing diff tests: {len(tests)}\n")
    covered_modules: list[str] = []
    uncovered_modules: list[str] = []
    for module_path, _ in sorted(funcs.items()):
        # Strip extension and path; match against test names.
        stem = Path(module_path).stem
        # Heuristic: test_<stem>_diff.py covers <stem>.py.
        if stem in tests:
            covered_modules.append(module_path)
        else:
            uncovered_modules.append(module_path)
    lines.append(f"## Covered modules ({len(covered_modules)})\n")
    for m in covered_modules:
        lines.append(f"  - {m}")
    lines.append(f"\n## Uncovered modules ({len(uncovered_modules)})\n")
    for m in uncovered_modules:
        funcs_in_module = funcs[m]
        lines.append(f"  - {m} ({len(funcs_in_module)} functions)")
    coverage = len(covered_modules) / len(funcs) * 100 if funcs else 0.0
    lines.append(f"\n## Coverage: {coverage:.1f}% modules")
    return "\n".join(lines) + "\n"


def main() -> None:
    funcs = enumerate_functions(AI_SRC)
    tests = diff_test_modules(DIFF_TESTS)
    report_text = report(funcs, tests)
    REPORT.write_text(report_text)
    print(report_text)


if __name__ == "__main__":
    main()
