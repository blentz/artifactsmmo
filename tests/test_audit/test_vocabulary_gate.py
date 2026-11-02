"""Tests for the vocabulary gate (spec 2026-10-18 §5 item 4): no `src/`
identifier names tier, rung, band, ladder or milestone outside its allowance.

The cases run on in-memory sources, and the last ones run on the real tree, so
the gate is held both to its rule and to the code it guards.
"""

import subprocess
import sys
from pathlib import Path

from artifactsmmo_cli.audit.vocabulary_gate import (
    ALLOWED,
    HOMES,
    GateResult,
    Hit,
    module_key,
    names_the_concept,
    orphans,
    parts,
    render,
    run_gate,
    scan,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
MODULE = "src/artifactsmmo_cli/ai/new_helper.py"


def _src_sources() -> dict[str, str]:
    return {str(path.relative_to(REPO_ROOT)): path.read_text()
            for path in sorted(SRC.rglob("*.py"))}


def test_a_new_tier_identifier_fails() -> None:
    """Review Focus 5: a fresh `tier_x` helper fails the gate, and so do the
    camelCase and plural spellings of the words."""
    source = ("def gear_tier(level: int) -> int:\n    return level // 10\n\n\n"
              "class IsMyGearBehindMyTier:\n    pass\n\n\n"
              "next_rungs = []\nMILESTONE = 10\nlevel_band = 3\n"
              "is_tiered = tiering_cap = banded = LadderedCost = subtier = 0\n")
    result = run_gate({MODULE: source}, homes={})
    assert not result.passed
    assert [hit.name for hit in result.violations] == [
        "gear_tier", "IsMyGearBehindMyTier", "next_rungs", "MILESTONE", "level_band",
        "is_tiered", "tiering_cap", "banded", "LadderedCost", "subtier"]
    assert result.violations[0] == Hit("ai/new_helper", 1, "gear_tier")


def test_a_comment_mentioning_tier_passes() -> None:
    """Prose is not a definition: comments, docstrings and strings that say
    tier, rung, band, ladder or milestone pass."""
    source = ('"""The deleted tier ladder: every rung, band and milestone."""\n\n'
              "# the tier ladder lived here\n"
              "LABEL = 'tier'\n")
    assert run_gate({MODULE: source}, homes={}).passed


def test_an_orphan_allow_entry_fails() -> None:
    """An allowance whose name no longer appears in its home fails, so the list
    cannot outlive the code it excuses."""
    source = "BAND_STEP = 1\n"
    homes = {"BAND_STEP": ("ai/new_helper",), "BAND_GONE": ("ai/new_helper",)}
    result = run_gate({MODULE: source}, homes=homes)
    assert result.violations == ()
    assert result.orphans == (("BAND_GONE", "ai/new_helper"),)
    assert not result.passed


def test_an_allowed_name_outside_its_home_fails() -> None:
    """Allowed by name AND module: a generic `band` is a priority band in the
    arbiter, and nothing anywhere else."""
    homes = {"band": ("ai/arbiter_select",)}
    elsewhere = run_gate({MODULE: "band = 1\n"}, homes=homes)
    assert elsewhere.violations == (Hit("ai/new_helper", 1, "band"),)
    home = run_gate({"src/artifactsmmo_cli/ai/arbiter_select.py": "band = 1\n"}, homes=homes)
    assert home.passed


def test_words_are_matched_on_parts_not_substrings() -> None:
    assert parts("CanICraftThisAtAll") == ["can", "i", "craft", "this", "at", "all"]
    assert parts("HTTPServer_v2") == ["http", "server", "v", "2"]
    assert names_the_concept("tiers")
    assert names_the_concept("TierCap")
    assert not names_the_concept("frontier")
    assert not names_the_concept("husband")
    assert not names_the_concept("bandwidth")
    assert not names_the_concept("tiara")
    for inflected in ("Tiered", "tiering", "banded", "laddered", "subtier", "rungs",
                      "Milestones", "midband"):
        assert names_the_concept(inflected), inflected
    assert scan("ai/x", "frontier = husband\n") == []


def test_orphans_reads_every_home_of_a_name() -> None:
    hits = [Hit("ai/a", 1, "band")]
    assert orphans(hits, {"band": ("ai/a", "ai/b")}) == (("band", "ai/b"),)


def test_module_key_strips_the_package_prefix() -> None:
    assert module_key("src/artifactsmmo_cli/ai/goals/gathering.py") == "ai/goals/gathering"
    assert module_key("src\\artifactsmmo_cli\\ai\\x.py") == "ai/x"


def test_render_names_each_violation_and_orphan() -> None:
    result = GateResult((Hit("ai/x", 3, "gear_tier"),), (("band", "ai/y"),))
    text = render(result)
    assert "ai/x:3: `gear_tier`" in text
    assert "orphan allowance: `band` no longer appears in ai/y" in text
    assert text.endswith("FAIL: 1 violation(s), 1 orphan(s)")
    assert render(GateResult((), ())) == "vocabulary gate: PASS"


def test_every_allowance_has_a_reason_and_a_home() -> None:
    assert set(ALLOWED) == set(HOMES)
    assert all(reason.strip() for reason in ALLOWED.values())
    assert all(HOMES.values())
    assert all(names_the_concept(name) for name in ALLOWED)


def test_src_is_clean() -> None:
    """The real tree: no identifier outside its allowance, and no orphan."""
    result = run_gate(_src_sources())
    assert result.violations == ()
    assert result.orphans == ()


def test_the_script_check_mode_passes_on_the_tree() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/gen_vocabulary_gate.py", "--check"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip().endswith("vocabulary gate: PASS")
