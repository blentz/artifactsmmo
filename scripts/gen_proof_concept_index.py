"""Scan formal/Formal for @concept/@property tags, regenerate the proof→concept
index, and cross-check against Manifest.lean. `--check` exits non-zero on drift."""

import re
import sys
from pathlib import Path

from artifactsmmo_cli.audit.proof_tags import (
    build_index,
    cross_check,
    parse_tags,
    render_index_markdown,
)

FORMAL = Path("formal/Formal")
INDEX = Path("docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md")
_MANIFEST_RE = re.compile(r"#check @Formal\.([A-Za-z0-9_.]+?)\.[A-Za-z0-9_']+")


def _module_name(path: Path) -> str:
    # formal/Formal/Liveness/Foo.lean -> Liveness.Foo ; formal/Formal/Bar.lean -> Bar
    rel = path.relative_to(FORMAL).with_suffix("")
    return ".".join(rel.parts)


def main(check: bool) -> int:
    module_tags = {}
    for p in sorted(FORMAL.rglob("*.lean")):
        tags = parse_tags(p.read_text())
        if tags is not None:
            module_tags[_module_name(p)] = tags
    manifest_modules = set(_MANIFEST_RE.findall((FORMAL / "Manifest.lean").read_text()))
    errors = cross_check(tagged=set(module_tags), manifest_modules=manifest_modules)
    rows = build_index(module_tags)
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    rendered = render_index_markdown(rows)
    if check:
        if errors:
            print("\n".join(errors))
            return 1
        if INDEX.exists() and INDEX.read_text() != rendered:
            print("PROOF_CONCEPT_INDEX.md is stale — run gen_proof_concept_index.py")
            return 1
        print("proof-concept index OK")
        return 0
    INDEX.write_text(rendered)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"wrote {INDEX} ({len(rows)} modules)")
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
