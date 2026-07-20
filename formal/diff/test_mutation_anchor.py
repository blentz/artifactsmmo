"""Unit tests for the mutation-anchor matcher.

The mutation gate pins each mutant to a literal source excerpt. Before this
module those anchors were applied with `str.replace(old, new, 1)`, which had two
holes: an anchor occurring twice mutated an arbitrary first occurrence with no
warning, and an anchor that had merely been re-indented read as missing.

These tests pin the three outcomes the gate must be able to tell apart:
found-exactly-once, missing, and ambiguous.
"""

import pytest

from formal.diff.mutation_anchor import (
    AnchorAmbiguous,
    AnchorNotFound,
    MatchKind,
    apply_anchor,
    find_anchor,
)


class TestExactMatch:
    def test_single_occurrence_is_found(self) -> None:
        src = "def f():\n    return 1\n"
        m = find_anchor(src, "    return 1")
        assert m.kind is MatchKind.EXACT
        assert src[m.start : m.end] == "    return 1"

    def test_apply_replaces_the_occurrence(self) -> None:
        src = "def f():\n    return 1\n"
        assert apply_anchor(src, "    return 1", "    return 2") == "def f():\n    return 2\n"

    def test_multiline_anchor(self) -> None:
        src = "def f():\n    if x:\n        return 1\n    return 0\n"
        out = apply_anchor(src, "    if x:\n        return 1", "    if y:\n        return 1")
        assert out == "def f():\n    if y:\n        return 1\n    return 0\n"


class TestAmbiguity:
    """The hole this module exists to close."""

    def test_two_occurrences_raises(self) -> None:
        src = "def f():\n    return 1\n\ndef g():\n    return 1\n"
        with pytest.raises(AnchorAmbiguous) as ei:
            find_anchor(src, "    return 1")
        assert "2" in str(ei.value)

    def test_apply_refuses_ambiguous(self) -> None:
        src = "a = 1\na = 1\n"
        with pytest.raises(AnchorAmbiguous):
            apply_anchor(src, "a = 1", "a = 2")

    def test_ambiguity_reported_before_mutation(self) -> None:
        """An ambiguous anchor must not silently mutate the first hit."""
        src = "x = 0\nx = 0\n"
        with pytest.raises(AnchorAmbiguous):
            apply_anchor(src, "x = 0", "x = 9")


class TestMissing:
    def test_absent_anchor_raises(self) -> None:
        with pytest.raises(AnchorNotFound):
            find_anchor("def f():\n    pass\n", "    return 1")

    def test_message_names_the_anchor(self) -> None:
        with pytest.raises(AnchorNotFound) as ei:
            find_anchor("a = 1\n", "zzz = 2")
        assert "zzz = 2" in str(ei.value)


class TestReindentTolerance:
    """An anchor whose indentation changed is REFLOWED, not missing."""

    def test_dedented_source_still_matches_indented_anchor(self) -> None:
        """Anchor recorded at 8 spaces; code has since moved out to 4."""
        src = "def f():\n    return 1\n"
        m = find_anchor(src, "        return 1")
        assert m.kind is MatchKind.REFLOWED
        assert m.indent == "    "

    def test_apply_preserves_actual_indent(self) -> None:
        src = "def f():\n    return 1\n"
        out = apply_anchor(src, "        return 1", "        return 2")
        assert out == "def f():\n    return 2\n"

    def test_multiline_relative_indent_preserved(self) -> None:
        src = "class C:\n    def f(self):\n        if x:\n            return 1\n"
        out = apply_anchor(src, "if x:\n    return 1", "if y:\n    return 1")
        assert out == "class C:\n    def f(self):\n        if y:\n            return 1\n"

    def test_reflowed_ambiguity_still_raises(self) -> None:
        src = "class C:\n    def f(self):\n        return 1\n    def g(self):\n        return 1\n"
        with pytest.raises(AnchorAmbiguous):
            find_anchor(src, "return 1")

    def test_exact_match_wins_over_reflowed(self) -> None:
        """Exact match preserves legacy behaviour; reflow is only a fallback.

        This anchor would resolve under either pass; the exact pass runs first,
        so the reported kind is EXACT and the splice is byte-for-byte.
        """
        src = "def f():\n    return 1\n"
        m = find_anchor(src, "    return 1")
        assert m.kind is MatchKind.EXACT


class TestBareSubstringAnchors:
    """Bare-substring anchors (e.g. `MAX_ACHIEVABLE_GAP = 5`) are legacy and are
    kept working by the exact pass. The exact pass runs first *by design*, so
    such an anchor can still resolve inside a comment or a longer expression --
    that hazard is not removed, it is made LOUD: the moment the same text also
    appears in real code, the match is ambiguous and the gate stops.
    """

    def test_comment_only_occurrence_still_resolves(self) -> None:
        """Documents the retained hazard rather than pretending it is fixed."""
        src = "class C:\n    # MAX_GAP = 5 is the old value\n    pass\n"
        assert find_anchor(src, "MAX_GAP = 5").kind is MatchKind.EXACT

    def test_comment_plus_real_code_is_ambiguous(self) -> None:
        """The actual protection: two candidate sites fail loudly."""
        src = "# MAX_GAP = 5 was the old value\nMAX_GAP = 5\n"
        with pytest.raises(AnchorAmbiguous):
            find_anchor(src, "MAX_GAP = 5")

    def test_exact_substring_inside_line_still_works(self) -> None:
        """Legacy anchors that are genuine substrings keep working."""
        src = "value = compute(a, b)\n"
        assert apply_anchor(src, "compute(a, b)", "compute(b, a)") == "value = compute(b, a)\n"


class TestBlankLineHandling:
    def test_blank_line_inside_anchor(self) -> None:
        src = "def f():\n    a = 1\n\n    b = 2\n"
        out = apply_anchor(src, "    a = 1\n\n    b = 2", "    a = 9\n\n    b = 2")
        assert "a = 9" in out

    def test_reindent_does_not_add_trailing_whitespace_to_blank_lines(self) -> None:
        src = "class C:\n    def f(self):\n        a = 1\n\n        b = 2\n"
        out = apply_anchor(src, "a = 1\n\n b = 2".replace(" b", "b"), "a = 9\n\nb = 2")
        assert "\n\n" in out
        assert " \n" not in out
