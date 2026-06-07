"""Lint the behavioral-completeness MATRIX: every `### <concept>` section must
carry all seven fields, each non-empty/non-placeholder, and every strategic field
must cite a source (a parenthetical). Keeps the audit honest and complete."""

import re

REQUIRED_FIELDS = [
    "Player → concept", "Concept → player", "Strategic uses",
    "Opportunity cost × tier", "Behavior coverage", "Proof coverage", "Gap + policy",
]
# Fields that assert strategy and therefore must cite a source.
_CITED_FIELDS = {"Strategic uses", "Opportunity cost × tier", "Gap + policy"}
_PLACEHOLDERS = ("tbd", "todo", "fixme", "xxx", "...")
_FIELD_RE = re.compile(r"^- \*\*(?P<name>[^*]+)\*\*:\s*(?P<body>.*)$")
_SECTION_RE = re.compile(r"^### (?P<concept>.+)$")


def lint_matrix(text: str) -> list[str]:
    """Return human-readable errors (empty = clean)."""
    errors: list[str] = []
    concept: str | None = None
    fields: dict[str, str] = {}

    def _flush() -> None:
        if concept is None:
            return
        for req in REQUIRED_FIELDS:
            body = fields.get(req)
            if body is None:
                errors.append(f"[{concept}] missing field: {req}")
                continue
            if not body or body.strip().lower() in _PLACEHOLDERS:
                errors.append(f"[{concept}] placeholder/empty field: {req}")
                continue
            if req in _CITED_FIELDS and "(" not in body:
                errors.append(f"[{concept}] citation required for field: {req}")

    for line in text.splitlines():
        ms = _SECTION_RE.match(line)
        if ms:
            _flush()
            concept = ms.group("concept").strip()
            fields = {}
            continue
        mf = _FIELD_RE.match(line)
        if mf and concept is not None:
            fields[mf.group("name").strip()] = mf.group("body").strip()
    _flush()
    return errors
