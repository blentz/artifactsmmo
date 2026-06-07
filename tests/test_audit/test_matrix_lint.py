from artifactsmmo_cli.audit.matrix_lint import REQUIRED_FIELDS, lint_matrix

_GOOD = """### tasks
- **Player → concept**: accept/complete/cancel/exchange (openapi /my/{name}/action/task/*)
- **Concept → player**: gold, tasks_coin, items, XP (docs: tasks)
- **Strategic uses**: steady gold + coin economy (docs)
- **Opportunity cost × tier**: T1 cheap; competes with gear gather (content_tiers.md)
- **Behavior coverage**: PursueTask/AcceptTask/CompleteTask/TaskExchange (tiers/means.py)
- **Proof coverage**: TaskDecision.req_none_pursues [dominance] (PROOF_CONCEPT_INDEX)
- **Gap + policy**: UNPROVEN — act; prove reachability (synthesis)
"""

_MISSING = "### bank\n- **Player → concept**: deposit/withdraw (openapi /my/.../bank)\n"


def test_lint_passes_complete_section():
    assert lint_matrix(_GOOD) == []


def test_lint_flags_missing_fields():
    errors = lint_matrix(_MISSING)
    assert any("bank" in e and "Concept → player" in e for e in errors)


def test_lint_flags_empty_or_placeholder_field():
    bad = _GOOD.replace("steady gold + coin economy (docs)", "TBD")
    errors = lint_matrix(bad)
    assert any("placeholder" in e.lower() for e in errors)


def test_lint_flags_uncited_claim():
    # A strategic field with no parenthetical citation.
    bad = _GOOD.replace("steady gold + coin economy (docs)", "steady gold economy")
    errors = lint_matrix(bad)
    assert any("citation" in e.lower() for e in errors)


def test_required_fields_match_spec():
    assert REQUIRED_FIELDS == [
        "Player → concept", "Concept → player", "Strategic uses",
        "Opportunity cost × tier", "Behavior coverage", "Proof coverage", "Gap + policy",
    ]
