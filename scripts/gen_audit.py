"""Generate `formal/Formal/Audit.lean` from `formal/Formal/Manifest.lean`.

Manifest.lean is the human-curated traceability list; Audit.lean is what the
safety axiom gate iterates. They used to be maintained by hand and had drifted
apart in both directions, so a theorem could carry a traceability row while
nothing ever scanned its axioms. Deriving one from the other removes that
failure mode. `--check` exits non-zero on drift.
"""

import sys
from pathlib import Path

from artifactsmmo_cli.audit.proof_tags import (
    manifest_audit_names,
    manifest_open_lines,
    render_audit_lean,
)

MANIFEST = Path("formal/Formal/Manifest.lean")
AUDIT = Path("formal/Formal/Audit.lean")


def main(check: bool) -> int:
    manifest = MANIFEST.read_text()
    names = manifest_audit_names(manifest)
    rendered = render_audit_lean(names, manifest_open_lines(manifest))
    if check:
        if AUDIT.read_text() != rendered:
            print("Audit.lean is stale — run `uv run python scripts/gen_audit.py`")
            return 1
        print(f"audit list OK ({len(names)} declarations)")
        return 0
    AUDIT.write_text(rendered)
    print(f"wrote {AUDIT} ({len(names)} declarations)")
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
