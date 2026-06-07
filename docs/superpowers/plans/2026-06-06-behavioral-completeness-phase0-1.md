# Behavioral Completeness — Phase 0–1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation (generated content-tier table, mechanically-checked concept↔proof traceability index, the audit matrix + completeness lint, leverage-scored gap backlog) and complete the behavioral-completeness audit that drives the bug-free-AI program.

**Architecture:** Pure, TDD'd logic lives in a new `src/artifactsmmo_cli/audit/` package (subject to the repo's 100% coverage gate). Thin live-data/CI wrappers live in `scripts/` and `formal/gate/`. Markdown artifacts live under `docs/behavioral_completeness/`. A new gate part fails the build if the proof↔concept index drifts.

**Tech Stack:** Python 3.13 (`uv`), pytest (100% coverage), bash gate scripts, Lean 4 module header tags. No new deps.

**Spec:** `docs/superpowers/specs/2026-06-06-behavioral-completeness-design.md`

---

## File structure

| File | Responsibility | New? |
|---|---|---|
| `src/artifactsmmo_cli/audit/__init__.py` | package marker | create |
| `src/artifactsmmo_cli/audit/content_tiers.py` | pure `derive_content_tiers(...)` clustering | create |
| `src/artifactsmmo_cli/audit/proof_tags.py` | pure tag parse + index build + Manifest cross-check | create |
| `src/artifactsmmo_cli/audit/matrix_lint.py` | pure matrix-row completeness check | create |
| `src/artifactsmmo_cli/audit/leverage.py` | pure gap leverage score + backlog sort | create |
| `scripts/gen_content_tiers.py` | live wrapper: GameData → `content_tiers.md` | create |
| `scripts/gen_proof_concept_index.py` | wrapper: scan `formal/Formal/**` → index md + check | create |
| `formal/gate/check_proof_concept_index.sh` | gate part calling the checker | create |
| `formal/gate.sh` | add the new gate part | modify |
| `docs/behavioral_completeness/MATRIX.md` | the audit matrix | create |
| `docs/behavioral_completeness/content_tiers.md` | generated tier table | create (generated) |
| `docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md` | generated inverse index | create (generated) |
| `docs/behavioral_completeness/BACKLOG.md` | ranked gap backlog | create (generated) |
| `pyproject.toml` | coverage omit for the two thin `scripts/` wrappers if needed | modify (only if scripts can't reach 100%) |
| tests under `tests/test_audit/` | unit tests for each pure module | create |

The 4 `audit/*.py` pure modules are fully unit-tested (100%). The `scripts/*.py` wrappers are thin (load data, call pure fns, write files); they are exercised by an integration test that runs them against a fixture and asserts the output file shape.

---

## Phase 0 — Foundation

### Task 1: content-tier clustering (pure)

**Files:**
- Create: `src/artifactsmmo_cli/audit/__init__.py` (empty), `src/artifactsmmo_cli/audit/content_tiers.py`
- Test: `tests/test_audit/__init__.py` (empty), `tests/test_audit/test_content_tiers.py`

- [ ] **Step 1: failing test** (`tests/test_audit/test_content_tiers.py`)

```python
"""derive_content_tiers clusters level-gated game content into capability-unlock tiers."""
from artifactsmmo_cli.audit.content_tiers import ContentTier, derive_content_tiers


def test_groups_items_monsters_resources_by_level_band():
    # Inputs are plain (code -> level) maps, as extracted from GameData.
    items = {"copper_dagger": 1, "iron_dagger": 10, "steel_dagger": 20}
    monsters = {"chicken": 1, "wolf": 10, "ogre": 20}
    resources = {"copper_rocks": 1, "iron_rocks": 10}
    tiers = derive_content_tiers(items, monsters, resources, band=10)
    # band=10 ⇒ tiers [1..10], [11..20], [21..30]
    assert [t.min_level for t in tiers] == [1, 11, 21]
    assert tiers[0].items == ["copper_dagger"]
    assert tiers[0].monsters == ["chicken"]
    assert tiers[0].resources == ["copper_rocks"]
    assert tiers[1].items == ["iron_dagger"]
    assert tiers[2].items == ["steel_dagger"]


def test_tier_is_sorted_and_named_by_band():
    tiers = derive_content_tiers({"a": 5}, {}, {}, band=10)
    assert len(tiers) == 1
    assert tiers[0].name == "T1 (levels 1-10)"
    assert tiers[0].min_level == 1 and tiers[0].max_level == 10


def test_empty_inputs_yield_no_tiers():
    assert derive_content_tiers({}, {}, {}, band=10) == []
```

- [ ] **Step 2: run, confirm fail**

Run: `uv run pytest tests/test_audit/test_content_tiers.py -v --no-cov`
Expected: FAIL — module not found.

- [ ] **Step 3: implement** (`src/artifactsmmo_cli/audit/content_tiers.py`)

```python
"""Cluster level-gated game content into capability-unlock tiers — the journey
axis of the behavioral-completeness audit. Pure: inputs are (code -> level) maps
extracted from GameData; no I/O. A tier is a band of `band` levels holding the
items/monsters/resources unlocked within it."""

from dataclasses import dataclass, field


@dataclass
class ContentTier:
    index: int
    name: str
    min_level: int
    max_level: int
    items: list[str] = field(default_factory=list)
    monsters: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)


def _band_index(level: int, band: int) -> int:
    return (max(1, level) - 1) // band


def derive_content_tiers(
    items: dict[str, int],
    monsters: dict[str, int],
    resources: dict[str, int],
    band: int = 10,
) -> list[ContentTier]:
    """Group content into `band`-wide level tiers. Returns tiers sorted by level,
    each listing the (sorted) codes unlocked in that band. Bands with no content
    in ANY category are omitted."""
    buckets: dict[int, ContentTier] = {}

    def _tier(level: int) -> ContentTier:
        bi = _band_index(level, band)
        if bi not in buckets:
            lo = bi * band + 1
            hi = lo + band - 1
            buckets[bi] = ContentTier(index=bi, name=f"T{bi + 1} (levels {lo}-{hi})",
                                      min_level=lo, max_level=hi)
        return buckets[bi]

    for code, lvl in items.items():
        _tier(lvl).items.append(code)
    for code, lvl in monsters.items():
        _tier(lvl).monsters.append(code)
    for code, lvl in resources.items():
        _tier(lvl).resources.append(code)
    for t in buckets.values():
        t.items.sort(); t.monsters.sort(); t.resources.sort()
    return [buckets[k] for k in sorted(buckets)]
```

- [ ] **Step 4: run, confirm pass**

Run: `uv run pytest tests/test_audit/test_content_tiers.py -v --no-cov`
Expected: PASS (3 tests).

- [ ] **Step 5: commit**

```bash
git add src/artifactsmmo_cli/audit/__init__.py src/artifactsmmo_cli/audit/content_tiers.py tests/test_audit/
git commit -m "feat(audit): pure content-tier clustering (journey axis)"
```

### Task 2: tier generator script + generated table

**Files:**
- Create: `scripts/gen_content_tiers.py`, `docs/behavioral_completeness/content_tiers.md` (generated output)
- Test: `tests/test_audit/test_gen_content_tiers.py`

- [ ] **Step 1: failing test** — assert the markdown renderer (pure, in `content_tiers.py`) produces a table. Add to `content_tiers.py` a `render_markdown(tiers) -> str`; test it:

```python
# tests/test_audit/test_gen_content_tiers.py
from artifactsmmo_cli.audit.content_tiers import derive_content_tiers, render_markdown


def test_render_markdown_has_header_and_one_row_per_tier():
    tiers = derive_content_tiers({"copper_dagger": 1}, {"chicken": 1}, {"copper_rocks": 1}, band=10)
    md = render_markdown(tiers)
    assert "| Tier | Levels | Items | Monsters | Resources |" in md
    assert "T1 (levels 1-10)" in md
    assert "copper_dagger" in md and "chicken" in md and "copper_rocks" in md
```

- [ ] **Step 2: run, confirm fail** — `uv run pytest tests/test_audit/test_gen_content_tiers.py -v --no-cov` (FAIL: no `render_markdown`).

- [ ] **Step 3: implement** — add to `content_tiers.py`:

```python
def render_markdown(tiers: list[ContentTier]) -> str:
    """Render tiers as a committed markdown table (the journey axis artifact)."""
    lines = [
        "# Content-unlock tiers (generated — do not hand-edit)",
        "",
        "Journey axis for the behavioral-completeness matrix. Regenerate with",
        "`uv run python scripts/gen_content_tiers.py`.",
        "",
        "| Tier | Levels | Items | Monsters | Resources |",
        "|---|---|---|---|---|",
    ]
    for t in tiers:
        lines.append(
            f"| {t.name.split(' ')[0]} | {t.min_level}-{t.max_level} | "
            f"{', '.join(t.items) or '—'} | {', '.join(t.monsters) or '—'} | "
            f"{', '.join(t.resources) or '—'} |"
        )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: run, confirm pass** — `uv run pytest tests/test_audit/test_gen_content_tiers.py -v --no-cov` (PASS).

- [ ] **Step 5: write the live wrapper script** (`scripts/gen_content_tiers.py`) — thin, NOT unit-covered (it does live I/O; add to coverage omit in Step 6 if the gate flags it):

```python
"""Generate docs/behavioral_completeness/content_tiers.md from live game data.
Run: uv run python scripts/gen_content_tiers.py  (needs TOKEN / API access)."""

from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.content_tiers import derive_content_tiers, render_markdown
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config


def main() -> None:
    ClientManager().initialize(Config.from_token_file(None))
    gd = GameData.load(ClientManager().client)
    items = {c: s.level for c, s in gd._item_stats.items()}
    monsters = dict(gd._monster_level)
    resources = {c: lvl for c, (_skill, lvl) in gd._resource_skill.items()}
    tiers = derive_content_tiers(items, monsters, resources, band=10)
    out = Path("docs/behavioral_completeness/content_tiers.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(tiers))
    print(f"wrote {out} ({len(tiers)} tiers)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: run it live, commit the generated table** (if API is unavailable in your environment, generate from the cached fixture the integration test uses and note it):

```bash
uv run python scripts/gen_content_tiers.py
# If coverage gate flags scripts/gen_content_tiers.py, add to [tool.coverage.run] omit in pyproject.toml:
#   omit = ["scripts/*"]
git add scripts/gen_content_tiers.py docs/behavioral_completeness/content_tiers.md pyproject.toml src/artifactsmmo_cli/audit/content_tiers.py tests/test_audit/test_gen_content_tiers.py
git commit -m "feat(audit): content-tier generator + generated journey-axis table"
```

### Task 3: proof tag parsing + index build (pure)

**Files:**
- Create: `src/artifactsmmo_cli/audit/proof_tags.py`
- Test: `tests/test_audit/test_proof_tags.py`

Tag format (one header line per module): `-- @concept: combat, monsters @property: safety, dominance`. Allowed concept tokens include the game concepts plus the pseudo-concept `core` (for abstract/infra modules). Allowed property tokens: `dominance`, `monotonicity`, `totality`, `no-deadlock`, `safety`, `reachability`.

- [ ] **Step 1: failing test**

```python
# tests/test_audit/test_proof_tags.py
import pytest
from artifactsmmo_cli.audit.proof_tags import ProofTags, parse_tags, build_index, cross_check


def test_parse_tags_extracts_concepts_and_properties():
    text = "-- @concept: combat, monsters @property: safety, dominance\nimport Foo\n"
    tags = parse_tags(text)
    assert tags == ProofTags(concepts=["combat", "monsters"], properties=["safety", "dominance"])


def test_parse_tags_missing_returns_none():
    assert parse_tags("import Foo\ntheorem t : True := trivial\n") is None


def test_parse_tags_rejects_unknown_property():
    with pytest.raises(ValueError, match="unknown property"):
        parse_tags("-- @concept: combat @property: optimality\n")


def test_build_index_rows_sorted_by_module():
    mods = {"Beta": ProofTags(["tasks"], ["safety"]), "Alpha": ProofTags(["bank"], ["totality"])}
    rows = build_index(mods)
    assert [r.module for r in rows] == ["Alpha", "Beta"]
    assert rows[0].concepts == ["bank"]


def test_cross_check_flags_manifest_module_without_tags():
    # Manifest references Gamma but Gamma has no tags ⇒ error listing Gamma.
    errors = cross_check(tagged={"Alpha"}, manifest_modules={"Alpha", "Gamma"})
    assert any("Gamma" in e for e in errors)


def test_cross_check_clean_when_all_tagged():
    assert cross_check(tagged={"Alpha", "Gamma"}, manifest_modules={"Alpha", "Gamma"}) == []
```

- [ ] **Step 2: run, confirm fail** — module not found.

- [ ] **Step 3: implement** (`src/artifactsmmo_cli/audit/proof_tags.py`)

```python
"""Parse `-- @concept: ... @property: ...` header tags from Lean modules and build
the inverse proof→concept index. Pure (operates on text + name sets); the live
file-walk wrapper lives in scripts/. Mechanically tying each proof to the game
concept(s) it models is what makes the traceability checked, not prose."""

import re
from dataclasses import dataclass

_ALLOWED_PROPERTIES = frozenset({
    "dominance", "monotonicity", "totality", "no-deadlock", "safety", "reachability",
})
_TAG_RE = re.compile(r"@concept:\s*([^@]+?)\s*@property:\s*(.+)")


@dataclass(frozen=True)
class ProofTags:
    concepts: list[str]
    properties: list[str]


@dataclass(frozen=True)
class IndexRow:
    module: str
    concepts: list[str]
    properties: list[str]


def _split(csv: str) -> list[str]:
    return [tok.strip() for tok in csv.split(",") if tok.strip()]


def parse_tags(text: str) -> ProofTags | None:
    """Return the first `@concept/@property` header in `text`, or None if absent.
    Raises ValueError on an unknown property token (truthfulness over silence)."""
    m = _TAG_RE.search(text)
    if m is None:
        return None
    concepts = _split(m.group(1))
    properties = _split(m.group(2))
    for p in properties:
        if p not in _ALLOWED_PROPERTIES:
            raise ValueError(f"unknown property tag: {p!r} (allowed: {sorted(_ALLOWED_PROPERTIES)})")
    return ProofTags(concepts=concepts, properties=properties)


def build_index(module_tags: dict[str, ProofTags]) -> list[IndexRow]:
    """Inverse index: one row per module → concepts + properties, sorted by module."""
    return [
        IndexRow(module=name, concepts=t.concepts, properties=t.properties)
        for name, t in sorted(module_tags.items())
    ]


def cross_check(tagged: set[str], manifest_modules: set[str]) -> list[str]:
    """Every module whose theorems are in Manifest.lean must carry tags. Returns a
    list of human-readable errors (empty = clean)."""
    return [
        f"module in Manifest but untagged (no @concept/@property): {m}"
        for m in sorted(manifest_modules - tagged)
    ]
```

- [ ] **Step 4: run, confirm pass** — `uv run pytest tests/test_audit/test_proof_tags.py -v --no-cov` (6 PASS).

- [ ] **Step 5: commit**

```bash
git add src/artifactsmmo_cli/audit/proof_tags.py tests/test_audit/test_proof_tags.py
git commit -m "feat(audit): proof-tag parser + inverse-index builder + Manifest cross-check"
```

### Task 4: index generator script + gate part

**Files:**
- Create: `scripts/gen_proof_concept_index.py`, `formal/gate/check_proof_concept_index.sh`, `docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md` (generated)
- Modify: `formal/gate.sh`
- Test: `tests/test_audit/test_gen_proof_concept_index.py`

- [ ] **Step 1: failing test** — add a pure `render_index_markdown(rows) -> str` to `proof_tags.py`; test it:

```python
# tests/test_audit/test_gen_proof_concept_index.py
from artifactsmmo_cli.audit.proof_tags import IndexRow, render_index_markdown


def test_render_index_lists_modules_concepts_properties():
    rows = [IndexRow("PlannerDepthBound", ["planner", "core"], ["safety", "reachability"])]
    md = render_index_markdown(rows)
    assert "| Module | Concepts | Properties |" in md
    assert "PlannerDepthBound" in md
    assert "planner, core" in md
    assert "safety, reachability" in md
```

- [ ] **Step 2: run, confirm fail.**

- [ ] **Step 3: implement** — add to `proof_tags.py`:

```python
def render_index_markdown(rows: list[IndexRow]) -> str:
    lines = [
        "# Proof → concept index (generated — do not hand-edit)",
        "",
        "Inverse of the MATRIX proof-coverage column. Regenerate with",
        "`uv run python scripts/gen_proof_concept_index.py`. A module with no",
        "concept tag, or a concept with no module, is a traceability gap.",
        "",
        "| Module | Concepts | Properties |",
        "|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r.module} | {', '.join(r.concepts)} | {', '.join(r.properties)} |")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: run, confirm pass.**

- [ ] **Step 5: write the live wrapper** (`scripts/gen_proof_concept_index.py`) — walks `formal/Formal/**/*.lean`, parses tags, extracts the module names referenced in `formal/Formal/Manifest.lean`, cross-checks, writes the index, and exits non-zero on any error (so the gate can call it with `--check`):

```python
"""Scan formal/Formal for @concept/@property tags, regenerate the proof→concept
index, and cross-check against Manifest.lean. `--check` exits non-zero on drift."""

import re
import sys
from pathlib import Path

from artifactsmmo_cli.audit.proof_tags import (
    build_index, cross_check, parse_tags, render_index_markdown,
)

FORMAL = Path("formal/Formal")
INDEX = Path("docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md")
_MANIFEST_RE = re.compile(r"#check @Formal\.([A-Za-z0-9_.]+?)\.[A-Za-z0-9_']+")


def _module_name(path: Path) -> str:
    # formal/Formal/Liveness/Foo.lean -> Liveness.Foo ; formal/Formal/Bar.lean -> Bar
    rel = path.relative_to(FORMAL).with_suffix("")
    return ".".join(rel.parts)


def main(check: bool) -> int:
    module_tags = {}
    for p in sorted(FORMAL.rglob("*.lean")):
        tags = parse_tags(p.read_text())
        if tags is not None:
            module_tags[_module_name(p)] = tags
    manifest_modules = set(_MANIFEST_RE.findall((FORMAL / "Manifest.lean").read_text()))
    errors = cross_check(tagged=set(module_tags), manifest_modules=manifest_modules)
    rows = build_index(module_tags)
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    rendered = render_index_markdown(rows)
    if check:
        if errors:
            print("\n".join(errors)); return 1
        if INDEX.exists() and INDEX.read_text() != rendered:
            print("PROOF_CONCEPT_INDEX.md is stale — run gen_proof_concept_index.py"); return 1
        print("proof-concept index OK"); return 0
    INDEX.write_text(rendered)
    if errors:
        print("\n".join(errors)); return 1
    print(f"wrote {INDEX} ({len(rows)} modules)"); return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
```

- [ ] **Step 6: gate part** (`formal/gate/check_proof_concept_index.sh`):

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."   # repo root
uv run python scripts/gen_proof_concept_index.py --check
```

`chmod +x formal/gate/check_proof_concept_index.sh`. Add to `formal/gate.sh` after the role-manifest part (line 15):

```bash
echo "== (b'') proof-concept index =="; bash "$HERE/gate/check_proof_concept_index.sh"
```

- [ ] **Step 7:** run `uv run pytest tests/test_audit/test_gen_proof_concept_index.py -v --no-cov` (PASS). Do NOT generate the index yet (modules untagged — that happens in Task 5). Commit the tooling:

```bash
chmod +x formal/gate/check_proof_concept_index.sh
git add scripts/gen_proof_concept_index.py formal/gate/check_proof_concept_index.sh formal/gate.sh src/artifactsmmo_cli/audit/proof_tags.py tests/test_audit/test_gen_proof_concept_index.py
git commit -m "feat(audit): proof-concept index generator + gate part (checks tag drift)"
```

### Task 5: back-tag the formal modules

**Files:**
- Modify: every `formal/Formal/**/*.lean` referenced in `Manifest.lean` (add one header tag line each)
- Create: `docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md` (generated)

- [ ] **Step 1:** list the modules needing tags:

Run: `uv run python scripts/gen_proof_concept_index.py --check`
Expected: FAIL listing every Manifest module that is untagged.

- [ ] **Step 2:** for EACH listed module, add a header tag line immediately after the opening `/-` block comment (or as the first line if none), mapping it to the game concept(s) it models and the property class(es) its theorems discharge. Use this concept vocabulary: `characters, maps, monsters, resources, items, crafting, tasks, bank, npcs, events, effects, grandexchange, achievements, badges, leaderboard, combat, planner, core`. Use `core` for abstract/structural modules that model no single game concept (e.g. `PlannerDepthBound` → `planner, core`; `CalculatePath` → `maps`; `RecycleProtection` → `items, crafting`; `PredictWin` → `combat, monsters`; `TaskBatch`/`TaskDecision`/`TaskFeasibility` → `tasks`; `BankSelection`/`InventoryCaps` → `bank, items`). Property tokens from the theorem character: `safety` (invariant/refused-when), `dominance`/`monotonicity` (ordering/mono), `totality`/`no-deadlock` (total dispatch/never-stuck), `reachability` (reaches/progress). Example header to add to `PlannerDepthBound.lean`:

```lean
-- @concept: planner, core @property: safety, reachability
```

Tag truthfully — the tag must reflect what the module's theorems actually prove (the audit's adversarial review will spot-check). Do this in batches; after each batch re-run the checker to see the remaining list shrink.

- [ ] **Step 3:** generate the index and confirm clean:

Run: `uv run python scripts/gen_proof_concept_index.py` then `uv run python scripts/gen_proof_concept_index.py --check`
Expected: `proof-concept index OK` (and `docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md` written, no stale/untagged errors).

- [ ] **Step 4:** confirm the formal gate part passes and nothing else broke:

Run: `cd formal && bash gate/check_proof_concept_index.sh && bash gate/check_no_orphan_modules.sh`
Expected: both OK.

- [ ] **Step 5: commit** (Lean header lines + generated index):

```bash
git add formal/Formal docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md
git commit -m "formal(audit): tag every Manifest module with @concept/@property; generate index"
```

### Task 6: matrix skeleton + completeness lint

**Files:**
- Create: `src/artifactsmmo_cli/audit/matrix_lint.py`, `docs/behavioral_completeness/MATRIX.md`
- Test: `tests/test_audit/test_matrix_lint.py`

The MATRIX is a markdown doc with one `### <concept>` section per concept, each containing the seven labelled fields from the spec. The lint parses it and fails if any concept section is missing a field or has an empty/placeholder field or an uncited strategic claim.

- [ ] **Step 1: failing test**

```python
# tests/test_audit/test_matrix_lint.py
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
```

- [ ] **Step 2: run, confirm fail.**

- [ ] **Step 3: implement** (`src/artifactsmmo_cli/audit/matrix_lint.py`)

```python
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
    concept = None
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
                errors.append(f"[{concept}] field needs a source citation '(...)': {req}")

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
```

- [ ] **Step 4: run, confirm pass** (5 tests).

- [ ] **Step 5:** create `docs/behavioral_completeness/MATRIX.md` with the column legend at top and ONE seeded, fully-cited example section (`### tasks`, copy `_GOOD` from the test) plus an empty `### <concept>` stub per remaining concept (these will fail lint until Phase 1 fills them — that's expected; the lint is the Phase-1 done-signal, not a Phase-0 gate). Commit:

```bash
git add src/artifactsmmo_cli/audit/matrix_lint.py docs/behavioral_completeness/MATRIX.md tests/test_audit/test_matrix_lint.py
git commit -m "feat(audit): matrix completeness lint + seeded MATRIX.md skeleton"
```

### Task 7: leverage scoring + backlog (pure)

**Files:**
- Create: `src/artifactsmmo_cli/audit/leverage.py`
- Test: `tests/test_audit/test_leverage.py`

- [ ] **Step 1: failing test**

```python
# tests/test_audit/test_leverage.py
from artifactsmmo_cli.audit.leverage import GapItem, leverage_score, rank_backlog


def test_score_is_product_of_factors():
    g = GapItem(concept="grandexchange", kind="MISSING", journey_impact=3, live_bottleneck=2, stall_risk=1)
    assert leverage_score(g) == 6


def test_ignore_kind_scores_zero():
    g = GapItem(concept="leaderboard", kind="IGNORE", journey_impact=3, live_bottleneck=3, stall_risk=3)
    assert leverage_score(g) == 0


def test_rank_sorts_descending_stable_by_concept():
    a = GapItem("a", "MISSING", 1, 1, 1)   # 1
    b = GapItem("b", "WRONG-POLICY", 3, 2, 2)  # 12
    c = GapItem("c", "THIN", 2, 2, 1)      # 4
    assert [g.concept for g in rank_backlog([a, b, c])] == ["b", "c", "a"]
```

- [ ] **Step 2: run, confirm fail.**

- [ ] **Step 3: implement** (`src/artifactsmmo_cli/audit/leverage.py`)

```python
"""Leverage scoring for the gap backlog: score = journey_impact * live_bottleneck
* stall_risk, except IGNORE gaps (deliberately not actioned) score 0. Pure."""

from dataclasses import dataclass

_VALID_KINDS = frozenset({"MISSING", "THIN", "UNPROVEN", "WRONG-POLICY", "IGNORE"})


@dataclass(frozen=True)
class GapItem:
    concept: str
    kind: str
    journey_impact: int   # 0-3: how much closing it unblocks tier progression
    live_bottleneck: int  # 0-3: is it the current binding constraint (from play data)
    stall_risk: int       # 0-3: does the gap cause stuck/incoherent behavior

    def __post_init__(self) -> None:
        if self.kind not in _VALID_KINDS:
            raise ValueError(f"unknown gap kind: {self.kind!r}")


def leverage_score(g: GapItem) -> int:
    if g.kind == "IGNORE":
        return 0
    return g.journey_impact * g.live_bottleneck * g.stall_risk


def rank_backlog(gaps: list[GapItem]) -> list[GapItem]:
    """Highest leverage first; ties keep input order (stable)."""
    return sorted(gaps, key=leverage_score, reverse=True)
```

- [ ] **Step 4: run, confirm pass** (3 tests).

- [ ] **Step 5: commit**

```bash
git add src/artifactsmmo_cli/audit/leverage.py tests/test_audit/test_leverage.py
git commit -m "feat(audit): gap leverage scoring + backlog ranking"
```

### Task 8: Phase-0 coverage + gate green

- [ ] **Step 1:** full suite + coverage:

Run: `uv run pytest tests/ -q`
Expected: 100% coverage maintained (the 4 `audit/*.py` pure modules fully covered; if a `scripts/*.py` wrapper line is uncovered, ensure `omit = ["scripts/*"]` is in `[tool.coverage.run]` of `pyproject.toml`, with a one-line comment that scripts are live-I/O wrappers exercised manually). All pass.

- [ ] **Step 2:** formal gate (the new index part is green because Task 5 tagged everything):

Run: `cd formal && bash gate.sh 2>&1 | tail -25`
Expected: every part OK, including `== (b'') proof-concept index ==`.

- [ ] **Step 3:** mypy + ruff:

Run: `uv run mypy src/artifactsmmo_cli/audit/ && uv run ruff check src/artifactsmmo_cli/audit/ scripts/`
Expected: clean.

- [ ] **Step 4: commit** any coverage-omit/config tweak:

```bash
git add pyproject.toml
git commit -m "chore(audit): coverage-exempt live-I/O script wrappers (justified)"
```

---

## Phase 1 — The audit (fill the matrix → backlog)

### Task 9: audit every concept row (research, lint-gated)

**Files:**
- Modify: `docs/behavioral_completeness/MATRIX.md`
- Create (generated at the end): `docs/behavioral_completeness/BACKLOG.md`
- Test: `tests/test_audit/test_matrix_complete.py`

This is the research deliverable. The procedure below is run ONCE PER CONCEPT; the concept list is the checklist. The `lint_matrix` gate is the done-signal.

Concepts to audit (each becomes a `### <concept>` section): `characters, maps, monsters, combat, resources, items, crafting, tasks, bank, npcs, events, effects, grandexchange, achievements, badges, leaderboard, simulation`.

- [ ] **Step 1: per-concept procedure** — for each concept, fill its seven fields, every strategic field citing a source:
  1. **Player → concept**: grep the openapi paths for the concept
     (`python3 -c "import json;d=json.load(open('openapi.json'));print([p for p in d['paths'] if '<concept>' in p])"`); list the actions; cite the path(s).
  2. **Concept → player**: from the relevant schema + game data (drops/rewards/gates/effects); cite the schema name or a `docs:` note.
  3. **Strategic uses**: fetch the artifactsmmo.com docs page for the concept (WebFetch the encyclopedia/guide section), summarize why/when to engage it; cite the URL.
  4. **Opportunity cost × tier**: reference `content_tiers.md`; for ≥2 representative tiers state the cost-vs-enables trade; cite `content_tiers.md`.
  5. **Behavior coverage**: grep `src/artifactsmmo_cli/ai/goals` and `tiers/means.py`/`guards.py` for handling; name the goal/means/guard or write "none"; cite the path.
  6. **Proof coverage**: look the concept up in `PROOF_CONCEPT_INDEX.md`; list the backing theorems + property classes, or "none"; cite the index.
  7. **Gap + policy**: classify (MISSING/THIN/UNPROVEN/WRONG-POLICY/IGNORE) and state the deliberate policy (act/exploit/ignore-with-reason); cite "synthesis".
  Run `uv run python -c "from artifactsmmo_cli.audit.matrix_lint import lint_matrix; import pathlib; print(lint_matrix(pathlib.Path('docs/behavioral_completeness/MATRIX.md').read_text()))"` after each concept; the error list shrinks.

- [ ] **Step 2: add the matrix-complete test** (`tests/test_audit/test_matrix_complete.py`) — this makes "audit done" a checked gate:

```python
"""The committed MATRIX.md must pass the completeness lint (every concept fully
filled + cited). This is the Phase-1 done-signal."""
import pathlib

from artifactsmmo_cli.audit.matrix_lint import lint_matrix


def test_committed_matrix_is_complete():
    text = pathlib.Path("docs/behavioral_completeness/MATRIX.md").read_text()
    errors = lint_matrix(text)
    assert errors == [], "MATRIX.md incomplete:\n" + "\n".join(errors)
```

- [ ] **Step 3: run** `uv run pytest tests/test_audit/test_matrix_complete.py -v --no-cov` — must PASS (all concepts filled). Iterate Step 1 until it does.

- [ ] **Step 4: generate the backlog** — for each concept's Gap, assign `journey_impact`/`live_bottleneck`/`stall_risk` (0-3; live_bottleneck from current traces/play data), build `GapItem`s, `rank_backlog`, and write `docs/behavioral_completeness/BACKLOG.md` (ranked table: concept · kind · score · one-line next-step). Do this in a small throwaway script invoked once, or hand-author from the scores; commit the resulting `BACKLOG.md`.

- [ ] **Step 5: commit**

```bash
git add docs/behavioral_completeness/MATRIX.md docs/behavioral_completeness/BACKLOG.md tests/test_audit/test_matrix_complete.py
git commit -m "docs(audit): complete behavioral-completeness matrix + ranked gap backlog"
```

### Task 10: program landing + adversarial honesty pass

- [ ] **Step 1:** adversarial review of the audit (the Phase-4 honesty pass): re-read each MATRIX row against the cited sources — is every strategic claim true to its citation? Spot-check 5 `@concept` tags against the modules' actual theorems (does `PredictWin` really model `combat`?). Fix any untruthful tag/claim; re-run the index checker + matrix lint.

- [ ] **Step 2:** update `docs/PLAN_planner_liveness.md` (or a new `docs/behavioral_completeness/README.md`) pointing to MATRIX/INDEX/BACKLOG and stating the program is in Phase-2 (gap closure), with the top-3 backlog items named.

- [ ] **Step 3:** full gates green (python 100% + coverage, formal `gate.sh`, mypy, ruff). Commit.

```bash
git add docs/behavioral_completeness/README.md docs/PLAN_planner_liveness.md
git commit -m "docs(audit): program README + Phase-2 entry (top gaps named)"
```

---

## Self-review notes (author)

- **Spec coverage:** Matrix→Tasks 6,9; content-tier table→Tasks 1,2; concept↔proof traceability (tagged headers + checked index + inverse + orphan-detection)→Tasks 3,4,5; 4 proof classes encoded as the property vocabulary→Task 3 (`_ALLOWED_PROPERTIES`) + used in Task 5 tagging; gap taxonomy + leverage prioritization→Tasks 7,9; sourcing (3 authorities, cited)→Task 9 procedure + matrix_lint citation check; decomposition Phase 0/1→all; honesty pass→Task 10.
- **Placeholder scan:** the only "TBD" strings are inside TEST fixtures asserting the lint REJECTS them — intended, not plan placeholders.
- **Type consistency:** `ContentTier`/`render_markdown` (T1,T2); `ProofTags`/`IndexRow`/`parse_tags`/`build_index`/`cross_check`/`render_index_markdown` (T3,T4) consistent; `GapItem`/`leverage_score`/`rank_backlog` (T7,T9); `REQUIRED_FIELDS`/`lint_matrix` (T6,T9).
- **Known execution reads (not placeholders):** the exact `[tool.coverage.run]` omit syntax in `pyproject.toml` and whether the live `scripts/*.py` need it (Task 2/8 handle conditionally); the artifactsmmo.com docs URLs per concept (fetched live in Task 9); the per-concept `journey_impact`/`stall_risk` scores (judgment in Task 9 Step 4, informed by `content_tiers.md` + traces).
