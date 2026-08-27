"""O6 census: no `Decision` prices anything except through `route_price`.

Prints the residuals and the Decision-class count.

CI gate: pass `--check` to exit non-zero when either residual is non-zero, or
when the sweep finds fewer `Decision` subclasses than the floor — a census that
passes because it looked at nothing reports a green obligation over an empty
set.

    uv run python scripts/gen_one_cost_model.py --check
"""

import pathlib
import sys

from artifactsmmo_cli.audit.one_cost_model import (
    MIN_DECISION_CLASSES,
    render,
    sweep,
)

PACKAGE = (pathlib.Path(__file__).resolve().parents[1]
           / "src" / "artifactsmmo_cli" / "ai" / "decisions")


def main() -> None:
    check = "--check" in sys.argv[1:]
    results = sweep(PACKAGE)
    print(render(results))
    if not check:
        return
    failed = False
    for key in ("second_pricer", "injected_pricer"):
        if results[key]:
            print(f"FAIL: {key} must be zero", file=sys.stderr)
            failed = True
    found = len(results["decision_classes"])
    if found < MIN_DECISION_CLASSES:
        print(f"FAIL: found {found} Decision classes, floor is "
              f"{MIN_DECISION_CLASSES} — the sweep is looking at too little to "
              f"mean anything", file=sys.stderr)
        failed = True
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
