"""Differential test: the real `refusal_fact_core.refusal_holds` (Phase 5-1)
must agree with the kernel-proved `Formal.RefusalFact.holds` over all inputs.

Item types are compared for equality only, so they are drawn from a small pool
of ids (plus "absent from game data") and mapped to strings on the Python side.
"""
from hypothesis import given
from hypothesis import strategies as st

from artifactsmmo_cli.ai.action_rejection import CATEGORICAL_REJECTIONS
from artifactsmmo_cli.ai.refusal_fact_core import refusal_holds
from formal.diff.oracle_client import run_oracle

_TYPES = ["utility", "ring", "artifact", "weapon"]
_type_id = st.integers(min_value=-1, max_value=len(_TYPES) - 1)


def _name(type_id: int) -> str | None:
    return None if type_id < 0 else _TYPES[type_id]


@given(
    http_code=st.sampled_from([*sorted(CATEGORICAL_REJECTIONS), 404, 478, 499]),
    recorded=_type_id, current=_type_id, worn=st.booleans(),
)
def test_refusal_holds_matches_oracle(http_code, recorded, current, worn):
    py = refusal_holds(http_code, _name(recorded), _name(current), worn)
    lean = run_oracle("refusal_holds", [[http_code, recorded, current, int(worn)]])[0]["holds"]
    assert py == lean, (http_code, recorded, current, worn, py, lean)
