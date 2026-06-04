"""Item 9: Differential-coverage audit (import-based v3).

Coverage sources (any one suffices to mark a module 'covered'):
  (a) Filename name-match: test_<stem>_diff.py exists for module <stem>.py.
  (b) Some test_*_diff.py imports `from artifactsmmo_cli.ai.<dotted> import ...`.
  (c) mutate.py registers a *_SRC constant pointing at the module path
      (i.e. the module is in the mutation gate's surface).

Output: formal/diff/coverage_audit_report.txt
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AI_SRC = REPO_ROOT / "src" / "artifactsmmo_cli" / "ai"
DIFF_TESTS = REPO_ROOT / "formal" / "diff"
MUTATE_PY = DIFF_TESTS / "mutate.py"
REPORT = DIFF_TESTS / "coverage_audit_report.txt"


def enumerate_functions(src: Path) -> dict[str, list[str]]:
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


def imports_from_diff_tests(diff_dir: Path) -> dict[str, set[str]]:
    """{dotted_module: {test_file_name, ...}}"""
    out: dict[str, set[str]] = defaultdict(set)
    prefix = "artifactsmmo_cli.ai."
    for path in diff_dir.glob("test_*_diff.py"):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(prefix):
                    sub = node.module[len(prefix):]
                    out[sub].add(path.name)
    return out


def diff_test_modules_by_name(diff_dir: Path) -> set[str]:
    out: set[str] = set()
    for path in diff_dir.glob("test_*_diff.py"):
        stem = path.stem
        if stem.startswith("test_") and stem.endswith("_diff"):
            out.add(stem[len("test_"):-len("_diff")])
    return out


def mutate_path_references(mutate_py: Path) -> set[str]:
    """Return the set of module paths (relative to src/artifactsmmo_cli/ai/)
    referenced via `ROOT / "src" / "artifactsmmo_cli" / "ai" / ...` chains
    in mutate.py."""
    text = mutate_py.read_text()
    # Match e.g. ROOT / "src" / "artifactsmmo_cli" / "ai" / "foo.py"
    # OR with nested dirs: ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "x.py"
    pattern = re.compile(
        r'ROOT\s*/\s*"src"\s*/\s*"artifactsmmo_cli"\s*/\s*"ai"((?:\s*/\s*"[^"]+")+)'
    )
    seg_pattern = re.compile(r'"([^"]+)"')
    paths: set[str] = set()
    for m in pattern.finditer(text):
        tail = m.group(1)
        segments = seg_pattern.findall(tail)
        if segments:
            paths.add("/".join(segments))
    return paths


def report(funcs, imports, name_match, mutate_paths) -> str:
    lines: list[str] = []
    lines.append("# Item 9 — Differential coverage audit (v3: imports + mutate)\n")
    lines.append("Source root: src/artifactsmmo_cli/ai/")
    lines.append("Diff tests: formal/diff/test_*_diff.py + mutate.py path refs")
    lines.append(f"Modules with functions: {len(funcs)}")
    total_funcs = sum(len(v) for v in funcs.values())
    lines.append(f"Total functions: {total_funcs}")
    lines.append(f"Diff test files: {len(name_match)}")
    lines.append(f"mutate.py SRC references: {len(mutate_paths)}\n")
    covered: list[str] = []
    uncovered: list[str] = []
    for m in sorted(funcs):
        dotted = m.removesuffix(".py").replace("/", ".")
        stem = Path(m).stem
        if dotted in imports or stem in name_match or m in mutate_paths:
            covered.append(m)
        else:
            uncovered.append(m)
    lines.append(f"## Covered modules ({len(covered)})\n")
    for m in covered:
        dotted = m.removesuffix(".py").replace("/", ".")
        importers = sorted(imports.get(dotted, []))
        tags = []
        if Path(m).stem in name_match:
            tags.append("name-match")
        if m in mutate_paths:
            tags.append("mutate.py")
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        if importers:
            lines.append(f"  - {m}{tag_str}  ←  {', '.join(importers)}")
        else:
            lines.append(f"  - {m}{tag_str}")
    lines.append(f"\n## Uncovered modules ({len(uncovered)})\n")
    for m in uncovered:
        lines.append(f"  - {m} ({len(funcs[m])} functions)")
    coverage = len(covered) / len(funcs) * 100 if funcs else 0.0
    lines.append(f"\n## Coverage: {coverage:.1f}% modules ({len(covered)}/{len(funcs)})")
    return "\n".join(lines) + "\n"


def main() -> None:
    funcs = enumerate_functions(AI_SRC)
    imports = imports_from_diff_tests(DIFF_TESTS)
    name_match = diff_test_modules_by_name(DIFF_TESTS)
    mutate_paths = mutate_path_references(MUTATE_PY)
    text = report(funcs, imports, name_match, mutate_paths)
    REPORT.write_text(text)
    for line in text.splitlines()[:10]:
        print(line)
    print(text.splitlines()[-1])
    print(f"(full report: {REPORT.relative_to(REPO_ROOT)})")


if __name__ == "__main__":
    main()
