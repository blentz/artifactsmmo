# TUI Sprite Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Draw the remaining TUI monster and NPC sprites (family-binned) and add a warn-level coverage audit that surfaces uncurated codes at startup.

**Architecture:** Monster/NPC map tiles already carry the real game `code` through `map_pane` into `sprite_registry`, so completing them is a pure data append to the curated dicts in `sprites.py` — no logic change. A new tui-layer audit class reads live `GameData` code sets, diffs them against the curated dict keys, and prints a non-fatal warning listing any uncurated codes. The procedural blob fallback stays as the renderer for anything still uncurated.

**Tech Stack:** Python 3.13, `uv` (all commands prefixed `uv run`), pytest, Textual TUI. Sprites are 8x8 palette-key char grids (`Sprite` value object, `validate_sprite` invariant).

## Global Constraints

- Run all Python via `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- Imports at top of file only. No inline imports. No `...` imports. No `TYPE_CHECKING`.
- ONE behavioral class per file. Pure data/schema modules may group declarations.
- Never catch `Exception`. No multi-level error handling. Use API data or fail.
- Test success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- All tests live under `tests/`.
- Every 8x8 sprite must pass `validate_sprite` (8 rows × 8 cols, every non-`.` char defined in its palette).

---

## Task 1: SpriteCoverageAudit module

Warn-level audit: given a `GameData`, report monster/NPC codes present in-game but absent from the curated sprite dicts. Non-fatal `print`, mirroring `GameData._audit_effect_coverage` (which uses `print("[game_data] ...")` + `capsys` tests).

**Files:**
- Create: `src/artifactsmmo_cli/tui/sprite_coverage_audit.py`
- Test: `tests/test_tui/test_sprite_coverage_audit.py`

**Interfaces:**
- Consumes: `GameData.all_monster_locations` (`Mapping[str, list[...]]`, keys = monster codes), `GameData.npc_locations` (`Mapping[str, tuple[int,int]]`, keys = npc codes); `MONSTER_SPRITES`/`NPC_SPRITES` (`dict[str, Sprite]`) from `sprites.py`.
- Produces: `class SpriteCoverageAudit` with `def run(self, game_data: GameData) -> None` that prints `[sprites] uncurated monsters: [...]` and `[sprites] uncurated npcs: [...]` for missing codes, and prints nothing when fully covered.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tui/test_sprite_coverage_audit.py
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.sprite_coverage_audit import SpriteCoverageAudit
from artifactsmmo_cli.tui.sprites import MONSTER_SPRITES, NPC_SPRITES


def _gd(monster_codes, npc_codes):
    gd = GameData()
    gd._monster_locations = {c: [(0, 0)] for c in monster_codes}
    gd.world.npc_tiles = {c: (0, 0) for c in npc_codes}
    return gd


def test_uncurated_monster_warns(capsys):
    curated = next(iter(MONSTER_SPRITES))
    SpriteCoverageAudit().run(_gd([curated, "made_up_beast"], []))
    out = capsys.readouterr().out
    assert "made_up_beast" in out and "uncurated monsters" in out
    assert curated not in out


def test_uncurated_npc_warns(capsys):
    curated = next(iter(NPC_SPRITES))
    SpriteCoverageAudit().run(_gd([], [curated, "made_up_vendor"]))
    out = capsys.readouterr().out
    assert "made_up_vendor" in out and "uncurated npcs" in out


def test_fully_covered_is_silent(capsys):
    SpriteCoverageAudit().run(_gd(list(MONSTER_SPRITES), list(NPC_SPRITES)))
    assert capsys.readouterr().out == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_sprite_coverage_audit.py -v`
Expected: FAIL — `ModuleNotFoundError: ...sprite_coverage_audit`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/artifactsmmo_cli/tui/sprite_coverage_audit.py
"""Warn-level audit: report entity codes present in-game but with no curated
sprite. Non-fatal — the procedural fallback still renders uncurated tiles.
Mirrors GameData._audit_effect_coverage in spirit (print, never raise)."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.sprites import MONSTER_SPRITES, NPC_SPRITES


class SpriteCoverageAudit:
    """Compares live monster/NPC codes against curated sprite dict keys."""

    def run(self, game_data: GameData) -> None:
        self._report("monsters", game_data.all_monster_locations.keys(), MONSTER_SPRITES.keys())
        self._report("npcs", game_data.npc_locations.keys(), NPC_SPRITES.keys())

    @staticmethod
    def _report(label: str, live_codes, curated_codes) -> None:
        uncurated = sorted(set(live_codes) - set(curated_codes))
        if uncurated:
            print(f"[sprites] uncurated {label}: {uncurated}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_sprite_coverage_audit.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Typecheck**

Run: `uv run mypy src/artifactsmmo_cli/tui/sprite_coverage_audit.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprite_coverage_audit.py tests/test_tui/test_sprite_coverage_audit.py
git commit -m "feat(tui): warn-level sprite coverage audit (monsters + npcs)"
```

---

## Task 2: Wire the audit into TUI startup

Run the audit once when the watch app starts, so uncurated codes surface in the log on every session.

**Files:**
- Modify: `src/artifactsmmo_cli/tui/app.py` (`WatchApp.__init__`, around line 73-76)
- Test: `tests/test_tui/test_app.py`

**Interfaces:**
- Consumes: `SpriteCoverageAudit.run(game_data)` from Task 1; `WatchApp.__init__(self, character: str, game_data: GameData)`.
- Produces: no new public surface — a side-effecting call in `__init__`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_tui/test_app.py
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.tui.sprites import NPC_SPRITES


def test_watchapp_init_audits_uncurated(capsys):
    gd = GameData()
    gd._monster_locations = {"made_up_beast": [(0, 0)]}
    gd.world.npc_tiles = {next(iter(NPC_SPRITES)): (0, 0)}
    WatchApp("robby", gd)
    out = capsys.readouterr().out
    assert "made_up_beast" in out and "uncurated monsters" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_app.py::test_watchapp_init_audits_uncurated -v`
Expected: FAIL — no `[sprites]` output.

- [ ] **Step 3: Wire the audit**

Add the import at the top of `app.py` (alongside the existing tui imports):

```python
from artifactsmmo_cli.tui.sprite_coverage_audit import SpriteCoverageAudit
```

At the end of `WatchApp.__init__` (after `self._game_data = game_data`), add:

```python
        SpriteCoverageAudit().run(game_data)
```

- [ ] **Step 4: Run test + full tui suite to verify pass, no regression**

Run: `uv run pytest tests/test_tui/ -v`
Expected: PASS (all, including the new test).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/app.py tests/test_tui/test_app.py
git commit -m "feat(tui): run sprite coverage audit at WatchApp startup"
```

---

## Task 3: `recolor` authoring helper for family variants

Family-binning is authoring-time: a shared base silhouette recolored per code. Add a tiny helper so family variants are one-liners (matches the existing `_player_with_tool` / `overlay_sprites` authoring helpers). No runtime family engine — output is ordinary `Sprite` entries.

**Files:**
- Modify: `src/artifactsmmo_cli/tui/sprites.py` (add helper near `overlay_sprites`)
- Test: `tests/test_tui/test_sprites.py`

**Interfaces:**
- Consumes: `Sprite`, `SPRITE_SIZE`, `validate_sprite` (already in `sprites.py`).
- Produces: `def recolor(base: Sprite, palette: dict[str, str]) -> Sprite` — returns a new `Sprite` with `base.rows` and the supplied palette (same shape, new colors). Used at authoring time to spin family variants.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_tui/test_sprites.py
from artifactsmmo_cli.tui.sprites import recolor, validate_sprite, Sprite


def test_recolor_keeps_shape_swaps_palette():
    base = Sprite(rows=("#" * 8,) * 8, palette={"#": "red"})
    out = recolor(base, {"#": "blue"})
    assert out.rows == base.rows
    assert out.palette == {"#": "blue"}
    validate_sprite("recolored", out)  # must stay a valid 8x8 with defined keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_sprites.py::test_recolor_keeps_shape_swaps_palette -v`
Expected: FAIL — `ImportError: cannot import name 'recolor'`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/artifactsmmo_cli/tui/sprites.py` (after `overlay_sprites`):

```python
def recolor(base: Sprite, palette: dict[str, str]) -> Sprite:
    """A family variant: same silhouette as `base`, new palette. Authoring-time
    helper for binning many codes onto one shared shape (e.g. slime colors)."""
    return Sprite(rows=base.rows, palette=palette)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_sprites.py::test_recolor_keeps_shape_swaps_palette -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprites.py tests/test_tui/test_sprites.py
git commit -m "feat(tui): recolor helper for authoring family sprite variants"
```

---

## Task 4: Enumerate the live roster gap (API-gated)

The exact monster/NPC rosters exist only behind the live game API. As of writing it returns **HTTP 502 (down)** — this task and Task 5/6 START only once `curl -s -o /dev/null -w '%{http_code}' https://api.artifactsmmo.com/monsters?size=1` returns `200`.

**Files:**
- Create: `docs/superpowers/plans/roster-gap.md` (scratch enumeration output — not shipped code)

**Interfaces:**
- Consumes: live `/monsters` and `/npcs` endpoints (paginated, `size=100`); the curated key sets `MONSTER_SPRITES` / `NPC_SPRITES`.
- Produces: two code lists — `missing_monsters`, `missing_npcs` — written to `roster-gap.md`, each grouped into a proposed family (`blob`, `small_beast`, `humanoid`, `undead`, `flyer`, `serpent`, `plant`, `giant`, `insectoid`, or `distinct`).

- [ ] **Step 1: Confirm the API is up**

Run: `curl -s -o /dev/null -w '%{http_code}\n' 'https://api.artifactsmmo.com/monsters?size=1'`
Expected: `200`. If `502`, STOP — the API is still down; skip to reviewing Tasks 1-3 and resume later.

- [ ] **Step 2: Fetch the rosters and compute the gap**

Run (writes `roster-gap.md`):

```bash
uv run python - <<'PY'
import httpx
from artifactsmmo_cli.tui.sprites import MONSTER_SPRITES, NPC_SPRITES

def all_codes(ep):
    codes, page = [], 1
    while True:
        d = httpx.get(f"https://api.artifactsmmo.com/{ep}", params={"size": 100, "page": page}).json()
        codes += [x["code"] for x in d["data"]]
        if page >= d["pages"]:
            break
        page += 1
    return codes

miss_m = sorted(set(all_codes("monsters")) - set(MONSTER_SPRITES))
miss_n = sorted(set(all_codes("npcs")) - set(NPC_SPRITES))
with open("docs/superpowers/plans/roster-gap.md", "w") as f:
    f.write(f"# Roster gap\n\n## missing_monsters ({len(miss_m)})\n")
    for c in miss_m:
        f.write(f"- [ ] {c}  (family: ?)\n")
    f.write(f"\n## missing_npcs ({len(miss_n)})\n")
    for c in miss_n:
        f.write(f"- [ ] {c}  (family: ?)\n")
print(f"monsters missing: {len(miss_m)}  npcs missing: {len(miss_n)}")
PY
```

Expected: prints the two gap counts and writes `roster-gap.md`.

- [ ] **Step 3: Bin each missing code into a family**

Edit `docs/superpowers/plans/roster-gap.md`: replace each `(family: ?)` with the chosen family, using the API's `type`/name hints and visual judgment. Rules:
- Shared silhouette per family; individuality via palette (and a small overpaint mark where useful).
- Assign `distinct` only when no family shape fits (e.g. a spider, bird, tree already are bespoke).
- Reuse existing curated shapes as bases where a curated relative exists (e.g. a new slime → the slime base).

- [ ] **Step 4: Commit the enumeration**

```bash
git add docs/superpowers/plans/roster-gap.md
git commit -m "docs(sprites): enumerated monster/npc roster gap + family bins"
```

---

## Task 5: Author + validate the missing monster sprites (API-gated)

For every code in `missing_monsters`, add a curated `Sprite`. Family members are one-line `recolor(...)` of a shared base; `distinct` members get a bespoke 8x8 grid. A data-driven test validates every curated monster sprite, so new entries are covered automatically.

**Files:**
- Modify: `src/artifactsmmo_cli/tui/sprites.py` (`MONSTER_SPRITES`; add family base shapes + any new palette colors), `src/artifactsmmo_cli/tui/palette.py` (new named colors)
- Test: `tests/test_tui/test_sprites.py`

**Interfaces:**
- Consumes: `recolor` (Task 3), `Sprite`, `validate_sprite`, existing curated bases (e.g. the slime shape).
- Produces: `MONSTER_SPRITES` covers every code in `missing_monsters`; each entry is 8x8-valid.

- [ ] **Step 1: Write the coverage + validity test (data-driven)**

```python
# add to tests/test_tui/test_sprites.py
import pytest
from artifactsmmo_cli.tui.sprites import MONSTER_SPRITES, validate_sprite


@pytest.mark.parametrize("code", sorted(MONSTER_SPRITES))
def test_every_curated_monster_sprite_is_valid(code):
    validate_sprite(code, MONSTER_SPRITES[code])
```

- [ ] **Step 2: Run it to confirm the current set is valid (baseline green)**

Run: `uv run pytest tests/test_tui/test_sprites.py -k every_curated_monster -v`
Expected: PASS for all existing codes (baseline before adding new ones).

- [ ] **Step 3: Author family base shapes needed by the gap**

For each family that has ≥1 member in `roster-gap.md` and no existing reusable base, add a concrete 8x8 base `Sprite` in `sprites.py` (module-level, near the existing bases). Example shape for a `humanoid` base (author the real ones per the families actually needed):

```python
_HUMANOID_BASE = Sprite(
    rows=(
        "..####..",
        ".#skks#.",
        ".#skks#.",
        "..#bb#..",
        ".#bbbb#.",
        ".#b##b#.",
        "..#..#..",
        ".##..##.",
    ),
    palette={"#": INK, "s": SKIN, "k": INK, "b": TUNIC},
)
```

Each base must pass `validate_sprite` (Step 5 enforces it).

- [ ] **Step 4: Add one `MONSTER_SPRITES` entry per missing code**

Family member (recolor a base with a new palette):

```python
    "sand_golem": recolor(_HUMANOID_BASE, {"#": INK, "s": KHAKI, "k": INK, "b": STONE}),
```

Distinct member (bespoke grid):

```python
    "giant_bat": Sprite(
        rows=(
            "........",
            "#......#",
            "##....##",
            "#w#..#w#",
            "#wwwwww#",
            "..w##w..",
            "...##...",
            "........",
        ),
        palette={"#": SLATE, "w": BAT_WING},
    ),
```

Add any new color constants to `palette.py` (e.g. `BAT_WING = "..."`) and import them at the top of `sprites.py`. Work through `roster-gap.md`, checking off each code as its entry lands.

- [ ] **Step 5: Run the validity test over the full expanded set**

Run: `uv run pytest tests/test_tui/test_sprites.py -k every_curated_monster -v`
Expected: PASS for every code, including all new ones (fails loudly on any bad grid or undefined palette key).

- [ ] **Step 6: Confirm zero uncurated monsters remain (audit is silent)**

Run: `uv run pytest tests/test_tui/test_sprite_coverage_audit.py -v`
Expected: PASS. (For a live check once the bot runs: no `[sprites] uncurated monsters` line.)

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprites.py src/artifactsmmo_cli/tui/palette.py tests/test_tui/test_sprites.py docs/superpowers/plans/roster-gap.md
git commit -m "feat(tui): draw remaining monster sprites (family-binned)"
```

---

## Task 6: Author + validate the missing NPC sprites (API-gated)

Same procedure as Task 5, for `missing_npcs` → `NPC_SPRITES`. NPCs are a smaller set; most are `humanoid`-family recolors (vendor/trader variants) with a few `distinct`.

**Files:**
- Modify: `src/artifactsmmo_cli/tui/sprites.py` (`NPC_SPRITES`), `src/artifactsmmo_cli/tui/palette.py` (new colors if any)
- Test: `tests/test_tui/test_sprites.py`

**Interfaces:**
- Consumes: `recolor`, `Sprite`, `validate_sprite`, the humanoid base from Task 5.
- Produces: `NPC_SPRITES` covers every code in `missing_npcs`; each entry is 8x8-valid.

- [ ] **Step 1: Write the coverage + validity test (data-driven)**

```python
# add to tests/test_tui/test_sprites.py
@pytest.mark.parametrize("code", sorted(NPC_SPRITES))
def test_every_curated_npc_sprite_is_valid(code):
    validate_sprite(code, NPC_SPRITES[code])
```

- [ ] **Step 2: Run it (baseline green)**

Run: `uv run pytest tests/test_tui/test_sprites.py -k every_curated_npc -v`
Expected: PASS for existing NPC codes.

- [ ] **Step 3: Add one `NPC_SPRITES` entry per missing code**

Recolor the humanoid base for vendor/trader variants, bespoke for the rest:

```python
    "gem_merchant": recolor(_HUMANOID_BASE, {"#": INK, "s": SKIN, "k": INK, "b": GOLD}),
```

Work through the `missing_npcs` list in `roster-gap.md`, checking off each code.

- [ ] **Step 4: Run the validity test over the full NPC set**

Run: `uv run pytest tests/test_tui/test_sprites.py -k every_curated_npc -v`
Expected: PASS for every code including new ones.

- [ ] **Step 5: Confirm the audit is silent for NPCs**

Run: `uv run pytest tests/test_tui/test_sprite_coverage_audit.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprites.py src/artifactsmmo_cli/tui/palette.py tests/test_tui/test_sprites.py docs/superpowers/plans/roster-gap.md
git commit -m "feat(tui): draw remaining npc sprites (family-binned)"
```

---

## Task 7: Full-suite gate

Confirm the whole change set meets the project's success criteria.

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite with coverage**

Run: `uv run pytest`
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage.

- [ ] **Step 2: Typecheck + lint**

Run: `uv run mypy src && uv run ruff check src tests`
Expected: no errors.

- [ ] **Step 3: Final commit if anything changed (else done)**

```bash
git status --short
```

Expected: clean, or commit any residual fixes with a descriptive message.

---

## Self-review notes

- **Spec coverage:** Task 1-2 = warn-level audit (spec §"Coverage audit"). Task 3 = family-binning authoring mechanism (spec §"Approach"). Task 5-6 = monster/NPC data additions (spec §"Data additions"). Task 4 = the live-roster sourcing dependency (spec §"Dependency / sequencing"). Structures/resources correctly untouched (spec "Out of scope"). Task 7 = testing criteria.
- **Unblocked now:** Tasks 1-3 need no live data (audit tests build `GameData` in memory; `recolor` is pure). Tasks 4-6 are explicitly API-gated with a 502 precheck.
- **No runtime family engine:** `recolor` runs at authoring time; `MONSTER_SPRITES`/`NPC_SPRITES` hold plain `Sprite` values. `sprite_registry` unchanged.
