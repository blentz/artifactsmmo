"""Tests for formal/gate/check_proof_citations.sh — the proof-citation gate.

The branch that added this found FIFTEEN places where a comment claimed more
than the code or the kernel supported, including `Formal.PlanModel
.min_plan_length_le_plan` cited as proved in four live locations while never
having been written. Every one of those named a `Formal.X.y` identifier, so a
mechanical resolver catches the whole class.

Three citation shapes are legitimate and the script must accept all three:
a DECLARATION (`theorem foo`), a MODULE (`Formal.Liveness.CycleStep` is a
file, not a theorem), and a RETRACTION (text that exists precisely to say a
theorem does NOT exist — this repo wrote three of those deliberately, and a
gate that failed them would push authors back toward silence).

The script is bash, so these drive it through `subprocess` and assert the
exit-code contract, exactly as `test_verify_collusion.py` does for its script.
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "formal" / "gate" / "check_proof_citations.sh"


def _run(base: Path) -> subprocess.CompletedProcess[str]:
    """Run the checker against `base` as its scan root."""
    return subprocess.run(
        ["bash", str(SCRIPT_PATH), str(base)],
        capture_output=True, text=True, check=False,
    )


def _tree(base: Path) -> None:
    """A minimal repo shape: one Lean module with one declaration."""
    (base / "formal" / "Formal").mkdir(parents=True)
    (base / "formal" / "diff").mkdir(parents=True)
    (base / "src").mkdir(parents=True)
    (base / "formal" / "Formal" / "Widget.lean").write_text(
        "namespace Formal.Widget\n\ntheorem holds (n : Nat) : n = n := rfl\n\nend Formal.Widget\n"
    )


def test_a_resolvable_declaration_passes(tmp_path: Path) -> None:
    _tree(tmp_path)
    (tmp_path / "src" / "ok.py").write_text('"""Proved in `Formal.Widget.holds`."""\n')
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "proof-citation check OK" in result.stdout


def test_an_unresolvable_declaration_fails_and_names_the_site(tmp_path: Path) -> None:
    """The defect this gate exists for: a named theorem that was never written."""
    _tree(tmp_path)
    (tmp_path / "src" / "bad.py").write_text(
        '"""Line one.\n\nProved in `Formal.Widget.never_written`.\n"""\n'
    )
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "Formal.Widget.never_written" in result.stdout
    assert "src/bad.py:3" in result.stdout


def test_a_module_reference_passes(tmp_path: Path) -> None:
    """`Formal.Liveness.CycleStep` is a FILE, not a declaration. Real citation."""
    _tree(tmp_path)
    (tmp_path / "formal" / "Formal" / "Liveness").mkdir()
    (tmp_path / "formal" / "Formal" / "Liveness" / "CycleStep.lean").write_text("-- module\n")
    (tmp_path / "src" / "mod.py").write_text('"""See `Formal.Liveness.CycleStep`."""\n')
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_tagged_retraction_passes(tmp_path: Path) -> None:
    """A retraction names a theorem in order to say it does NOT exist."""
    _tree(tmp_path)
    (tmp_path / "src" / "retracted.py").write_text(
        '"""The citation that stood here, NOT-PROVED: `Formal.Widget.never_written`,\n'
        'was false — that theorem was never written."""\n'
    )
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_an_untagged_mention_of_a_missing_theorem_still_fails(tmp_path: Path) -> None:
    """The retraction tag must be load-bearing: without it, the same prose fails.

    Otherwise the tag would be decoration and any phrasing would slip through.
    """
    _tree(tmp_path)
    (tmp_path / "src" / "untagged.py").write_text(
        '"""That theorem `Formal.Widget.never_written` was never written."""\n'
    )
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "Formal.Widget.never_written" in result.stdout


def test_formal_diff_is_scanned(tmp_path: Path) -> None:
    """The differential harnesses exist to bind Python to Lean; they are in scope."""
    _tree(tmp_path)
    (tmp_path / "formal" / "diff" / "test_x_diff.py").write_text(
        '"""Oracle for `Formal.Widget.never_written`."""\n'
    )
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "formal/diff/test_x_diff.py" in result.stdout


def test_tests_directory_is_not_scanned(tmp_path: Path) -> None:
    """Out of scope by decision: a stale citation in a test misleads but does
    not misrepresent shipped behaviour."""
    _tree(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_y.py").write_text(
        '"""Refers to `Formal.Widget.never_written`."""\n'
    )
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_reports_every_violation_not_just_the_first(tmp_path: Path) -> None:
    _tree(tmp_path)
    (tmp_path / "src" / "one.py").write_text('"""`Formal.Widget.gone_a`."""\n')
    (tmp_path / "src" / "two.py").write_text('"""`Formal.Widget.gone_b`."""\n')
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "Formal.Widget.gone_a" in result.stdout
    assert "Formal.Widget.gone_b" in result.stdout


def test_the_real_repository_passes() -> None:
    """The live tree must be clean — this is the gate's actual job."""
    result = _run(REPO_ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
