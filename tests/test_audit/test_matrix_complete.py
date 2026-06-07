"""The committed MATRIX.md must pass the completeness lint (every concept fully
filled + cited). This is the Phase-1 done-signal."""
import pathlib

from artifactsmmo_cli.audit.matrix_lint import lint_matrix


def test_committed_matrix_is_complete():
    text = pathlib.Path("docs/behavioral_completeness/MATRIX.md").read_text()
    errors = lint_matrix(text)
    assert errors == [], "MATRIX.md incomplete:\n" + "\n".join(errors)
