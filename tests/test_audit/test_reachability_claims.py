"""Tests for the reachability-claim census — the gate that fails when a comment
says live code has no caller.

The wave-3b deletion pass found three such comments; the worst, on
`ai/obtain_sources`, declared "INERT — nothing calls this yet" while eleven
production modules imported it and both plan producers ran through it. Acting
on that comment takes out the planner. Every case below is written against
that shape: a claim, a subject, and a graph that either agrees or does not.

The census must also LEAVE TRUE CLAIMS ALONE. `player._tree_band_adequate`
("nothing calls this method any more — a deliberate deferral") and
`tiers/progression_tree_core.potion_type_weight` (retained on purpose with its
Lean mirror) are both true and both must stay green, so the last tests here
drive the real tree.
"""

from pathlib import Path

from artifactsmmo_cli.audit.reachability_claims import (
    MIN_CLAIMS,
    Claim,
    Verdict,
    _reached_symbol,
    build_index,
    find_claims,
    module_name,
    render_register,
    run_census,
    summary_line,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _verdicts(sources: dict[str, str]) -> dict[str, Verdict]:
    return {f"{v.claim.module}:{v.claim.lineno}": v for v in run_census(sources)}


def test_a_module_claiming_no_caller_while_imported_is_false() -> None:
    """The obtain_sources shape, reduced: a module docstring says nothing
    consumes it and another production module imports it."""
    sources = {
        "src/pkg/inert.py": '"""INERT — nothing calls this yet."""\n\n\ndef f() -> int:\n    return 1\n',
        "src/pkg/user.py": "from pkg.inert import f\n\nX = f()\n",
    }
    verdict = _verdicts(sources)["pkg.inert:1"]
    assert verdict.is_false
    assert verdict.reached_by == ("pkg.user",)
    assert verdict.claim.kind == "module"
    assert verdict.claim.subject == "pkg.inert"


def test_a_module_claim_with_no_importer_is_true() -> None:
    sources = {
        "src/pkg/inert.py": '"""INERT — nothing consumes this yet."""\n\n\ndef f() -> int:\n    return 1\n',
        "src/pkg/other.py": "Y = 2\n",
    }
    verdict = _verdicts(sources)["pkg.inert:1"]
    assert not verdict.is_false
    assert verdict.reached_by == ()


def test_a_claim_inside_a_function_resolves_to_that_function() -> None:
    """Containment is the resolution rule: a docstring claim is about its own
    definition, not about the module it sits in."""
    sources = {
        "src/pkg/a.py": 'def kept() -> int:\n    """No production caller today."""\n    return 1\n',
        "src/pkg/b.py": "from pkg.a import kept\n\nZ = kept()\n",
    }
    verdict = _verdicts(sources)["pkg.a:2"]
    assert verdict.claim.kind == "symbol"
    assert verdict.claim.subject == "kept"
    assert verdict.is_false
    assert verdict.reached_by == ("pkg.b:1", "pkg.b:3")


def test_a_function_referenced_only_inside_its_own_body_stays_true() -> None:
    """Recursion is not a caller — the potion_type_weight shape."""
    sources = {
        "src/pkg/a.py": (
            'def kept(n: int) -> int:\n'
            '    """Has no production caller."""\n'
            "    return kept(n - 1)\n"
        ),
    }
    assert not _verdicts(sources)["pkg.a:2"].is_false


def test_an_attribute_on_a_plain_object_is_not_a_caller() -> None:
    """`RequirementGraph.is_obtainable` must not count as a caller of
    `tiers/skill_grind_target.is_obtainable`. Attribute names collide; only a
    reference through an imported MODULE counts for a module-level name."""
    sources = {
        "src/pkg/a.py": 'def is_obtainable() -> int:\n    """NO PRODUCTION CALLER."""\n    return 1\n',
        "src/pkg/b.py": (
            "class G:\n    def is_obtainable(self) -> int:\n        return 2\n"
            "\n\ndef go(g: G) -> int:\n    return g.is_obtainable()\n"
        ),
    }
    assert not _verdicts(sources)["pkg.a:2"].is_false


def test_a_reference_through_an_imported_module_is_a_caller() -> None:
    sources = {
        "src/pkg/a.py": 'def solo() -> int:\n    """Has no caller yet."""\n    return 1\n',
        "src/pkg/b.py": "from pkg import a\n\n\ndef go() -> int:\n    return a.solo()\n",
    }
    verdict = _verdicts(sources)["pkg.a:2"]
    assert verdict.is_false
    assert verdict.reached_by == ("pkg.b:5",)


def test_a_method_is_reached_through_a_plain_attribute() -> None:
    """A method has no other calling form, so attribute references DO count."""
    sources = {
        "src/pkg/a.py": (
            "class C:\n"
            "    def deferred(self) -> int:\n"
            '        """Nothing calls this method any more."""\n'
            "        return 1\n"
        ),
        "src/pkg/b.py": "from pkg.a import C\n\n\ndef go(c: C) -> int:\n    return c.deferred()\n",
    }
    verdict = _verdicts(sources)["pkg.a:3"]
    assert verdict.claim.subject == "deferred"
    assert verdict.is_false


def test_an_uncalled_method_is_true() -> None:
    sources = {
        "src/pkg/a.py": (
            "class C:\n"
            "    def deferred(self) -> int:\n"
            '        """Nothing calls this method any more."""\n'
            "        return 1\n"
        ),
    }
    assert not _verdicts(sources)["pkg.a:3"].is_false


def test_a_past_tense_frame_is_not_a_claim() -> None:
    """This repo writes true history about deleted code — "leaving zero
    callers", "they had zero callers". Gating on those is pure noise."""
    sources = {
        "src/pkg/a.py": (
            '"""The search it fed was deleted, leaving zero callers, and as of\n'
            'this commit they had zero readers."""\n\n\ndef f() -> int:\n    return 1\n'
        ),
        "src/pkg/b.py": "from pkg.a import f\n\nX = f()\n",
    }
    assert run_census(sources) == []


def test_a_trailing_past_tense_frame_is_not_a_claim() -> None:
    """"NO production caller ever passed one" and "each one has no reader
    left" both describe things already removed."""
    sources = {
        "src/pkg/a.py": (
            '"""NO production caller ever passed one, and each removed parameter\n'
            'has no reader left."""\n\n\ndef f() -> int:\n    return 1\n'
        ),
        "src/pkg/b.py": "from pkg.a import f\n\nX = f()\n",
    }
    assert run_census(sources) == []


def test_an_explicitly_named_subject_is_used_instead_of_containment() -> None:
    sources = {
        "src/pkg/a.py": (
            "def helper() -> int:\n"
            "    return 1\n"
            "\n"
            "\n"
            "def caller() -> int:\n"
            '    """Nothing calls `helper`."""\n'
            "    return 2\n"
        ),
    }
    verdict = _verdicts(sources)["pkg.a:6"]
    assert verdict.claim.subject == "helper"
    assert not verdict.is_false


def test_a_named_subject_that_no_longer_exists_is_skipped() -> None:
    """A note about a deletion names something with nothing left to verify."""
    sources = {"src/pkg/a.py": '"""Nothing calls `objective_roots`."""\n'}
    assert run_census(sources) == []


def test_the_census_does_not_sweep_its_own_source() -> None:
    """It must quote the phrasings it matches, so its own prose would trip it."""
    path = "src/artifactsmmo_cli/audit/reachability_claims.py"
    text = (REPO_ROOT / path).read_text()
    assert "nothing calls this" in text.lower()
    assert find_claims({path: text}, build_index({path: text})) == []


def test_a_relative_import_resolves_to_the_same_module() -> None:
    sources = {
        "src/pkg/a.py": '"""Nothing consumes it yet."""\n\n\ndef f() -> int:\n    return 1\n',
        "src/pkg/b.py": "from .a import f\n\nX = f()\n",
    }
    assert _verdicts(sources)["pkg.a:1"].is_false


def test_a_bare_relative_import_resolves_to_the_package() -> None:
    sources = {
        "src/pkg/__init__.py": "VALUE = 1\n",
        "src/pkg/a.py": '"""Nothing consumes it yet."""\n\n\ndef f() -> int:\n    return 1\n',
        "src/pkg/b.py": "from . import a\n\nX = a.f()\n",
    }
    assert _verdicts(sources)["pkg.a:1"].is_false
    assert module_name("src/pkg/__init__.py") == "pkg"


def test_a_plain_import_statement_reaches_the_module() -> None:
    sources = {
        "src/pkg/a.py": '"""Nothing consumes it yet."""\n\n\ndef f() -> int:\n    return 1\n',
        "src/pkg/b.py": "import pkg.a as alias\n\nX = alias.f()\n",
    }
    assert _verdicts(sources)["pkg.a:1"].is_false


def test_module_name_handles_paths_outside_src() -> None:
    assert module_name("pkg/a.py") == "pkg.a"
    assert module_name("src/pkg/a.py") == "pkg.a"


def test_a_subject_with_no_definition_in_its_module_is_never_self_excluded() -> None:
    """Guard for the `owner is None` arm: a hand-built claim whose subject the
    module does not define still gets checked against the whole graph."""
    sources = {"src/pkg/a.py": "def f() -> int:\n    return 1\n"}
    index = build_index(sources)
    claim = Claim("pkg.a", 1, "has no caller", "f", "symbol")
    assert _reached_symbol(claim, index) == ()


def test_render_register_shows_true_false_and_truncates_long_reach_lists() -> None:
    sources = {
        "src/pkg/a.py": '"""Nothing consumes it yet."""\n\n\ndef f() -> int:\n    return 1\n',
        "src/pkg/b.py": "from pkg.a import f\n",
        "src/pkg/c.py": "from pkg.a import f\n",
        "src/pkg/d.py": "from pkg.a import f\n",
        "src/pkg/e.py": "from pkg.a import f\n",
        "src/pkg/kept.py": 'def solo() -> int:\n    """Has no production caller."""\n    return 1\n',
    }
    register = render_register(run_census(sources))
    assert "FALSE — reached by pkg.b, pkg.c, pkg.d (+1 more)" in register
    assert "true — no production caller" in register


def test_summary_line_counts_both_verdicts() -> None:
    sources = {
        "src/pkg/a.py": '"""Nothing consumes it yet."""\n\n\ndef f() -> int:\n    return 1\n',
        "src/pkg/b.py": "from pkg.a import f\n",
        "src/pkg/kept.py": 'def solo() -> int:\n    """Has no production caller."""\n    return 1\n',
    }
    line = summary_line(run_census(sources))
    assert line == "reachability-claim census: 2 claims swept, 1 verified true, 1 FALSE"


def _real_sources() -> dict[str, str]:
    src = REPO_ROOT / "src"
    return {
        str(path.relative_to(REPO_ROOT)).replace("\\", "/"): path.read_text()
        for path in sorted(src.rglob("*.py"))
    }


def test_the_real_tree_carries_no_false_reachability_claim() -> None:
    """The gate's actual job."""
    false_claims = [v for v in run_census(_real_sources()) if v.is_false]
    assert false_claims == [], render_register(false_claims)


def test_the_real_sweep_meets_its_lower_bound() -> None:
    """A sweep that silently stops finding claims must fail, not report clean."""
    verdicts = run_census(_real_sources())
    assert len(verdicts) >= MIN_CLAIMS


def test_the_known_true_claims_are_swept_and_verified() -> None:
    """The deliberate keeps: a deferred method and the retained potion pair.

    If subject resolution regressed, these would vanish from the register and
    the census would go quietly blind on exactly the shape it exists for.
    """
    subjects = {v.claim.subject: v for v in run_census(_real_sources())}
    assert not subjects["_tree_band_adequate"].is_false
    assert not subjects["potion_type_weight"].is_false
    assert not subjects["is_obtainable"].is_false
