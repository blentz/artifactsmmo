# PLAN: Adversarial Review Fixes

Tracking doc for fixing all issues from the 2026-05-25 adversarial review.
Baseline: 2243 passed, 97% coverage (274 lines uncovered), 4 ResourceWarnings
(unclosed SQLite + live-API SSL sockets). Suite currently hits the LIVE game API.

## Decisions (locked)
- **C2**: AI layer (`ai/`) raises on missing API data; display commands render an
  explicit missing-field marker (`—`), never silent `0`/`"N/A"`.
- **Integration tests**: convert to mocked/offline. No live network in the suite.
- **W5**: refactor `commands/info.py` (1708) and `ai/player.py` (1282) this effort.
- **Coverage**: write tests to true 100%, then enforce `--cov-fail-under=100`.

## Phases (execute in order; each ends green: `uv run pytest`, `uv run mypy src`, `uv run ruff check`)

### P1 — Offline, deterministic suite  ✅ prerequisite for trustworthy coverage
- [ ] Convert `tests/test_integration.py` to mocked responses; remove all runtime
      `pytest.skip()` (lines 72,247,332,349,353,373) and `except Exception` (370,444,462).
- [ ] Add `addopts -m "not integration"`? — NO: tests become offline, keep them running.
- [ ] Kill live API calls in suite → no SSL ResourceWarnings.

### P2 — Resource cleanup (N3, warnings)
- [ ] `LearningStore`: context-manager / explicit `close()`; dispose SQLite engine.
      Close all stores opened in tests. → 0 ResourceWarnings.

### P3 — De-nest error handling (W1)
- [ ] `client_manager.py:180-219` `_handle_non_standard_status_error` — flatten to one level.
- [ ] `ai/learning/scalarizer.py:80-100` — flatten nested try.

### P4 — Brittle cooldown handling (W4)
- [ ] `ai/player.py` retry: replace substring match on `"HTTP 499"`/`"496"` + `sleep(1)`
      with structured status-code handling from the API error object.

### P5 — C2 no-defaulting
- [ ] `ai/` (actions, goals, game_data, player): raise `MissingApiData` on absent required fields.
- [ ] Display commands (info, character, account, bank): explicit `MISSING` marker render.

### P6 — W5 refactor god files
- [ ] Split `commands/info.py` into per-domain modules (items/monsters/resources/maps/...).
- [ ] Split `ai/player.py` (sense / plan / act / logging / recovery).

### P7 — N1 one-class-per-file (22 files)
- [ ] Split each multi-class file OR amend CLAUDE.md if rule is intentionally relaxed
      for dataclass-pairs/enums. (Confirm with user during P7.)

### P8 — Coverage to 100% + enforce
- [ ] Cover 274 lines (esp. `play.py` 35%, `helpers.py` 80%, `craft.py` 93%).
- [ ] pyproject addopts: `--cov=src/artifactsmmo_cli --cov-report=term-missing
      --cov-fail-under=100 --strict-markers -W error`.

### P9 — mypy strict is NOT clean (NEW finding, not in original review)
- [ ] `uv run mypy src` reports **129 errors in 11 files** on main (pre-existing).
      CLAUDE.md demands strict/0 errors. Mostly float-vs-int arg types in
      commands/action.py + others. Must reach 0.
- [ ] Tests are not in mypy scope at all (no files/packages in [tool.mypy]) —
      decide whether to bring tests under mypy (currently test_info.py has 192 errors).

## Status log
- 2026-05-25: plan created, baseline captured (2243 pass, 97% cov, 4 warnings).
- 2026-05-25: P1 DONE — integration tests offline+mocked, no skips/except Exception. Committed.
- 2026-05-25: P2 DONE — LearningStore weakref.finalize disposes engine; suite is 0-warning under -W error (2244 pass). Committed.
- 2026-05-25: Discovered P9 — 129 pre-existing mypy-strict errors on main. Added phase.
- Next: P3 (de-nest error handling) then P4/P5/P6/P7/P8/P9.
