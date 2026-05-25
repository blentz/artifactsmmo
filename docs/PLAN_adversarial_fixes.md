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

### P10 — latent runtime bugs surfaced by P9 (NEW, mock-hidden)
- [ ] `APIWrapper.action_fight` calls `action_fight_sync` without required `body`
      → real TypeError. `combat.py` callers pass body. `# type: ignore[call-arg]`
      in client_manager.py:107. Fix: accept+forward body; update test.
- [ ] `commands/trade.py orders` forwards `seller=` but endpoint param is `account=`
      → real TypeError. `# type: ignore[call-arg]`. test_trade.py:320 asserts the bug.
- [ ] `client_manager.py:242` timeout int vs httpx.Timeout — benign; test asserts
      literal int. `# type: ignore[arg-type]`. Lowest priority.
- All three are W3 made concrete: mocked `.sync` never validated the call signature.

## Status log
- 2026-05-25: plan created, baseline captured (2243 pass, 97% cov, 4 warnings).
- 2026-05-25: P1 DONE — integration tests offline+mocked, no skips/except Exception. Committed.
- 2026-05-25: P2 DONE — LearningStore weakref.finalize disposes engine; suite is 0-warning under -W error (2244 pass). Committed.
- 2026-05-25: Discovered P9 — 129 pre-existing mypy-strict errors on main. Added phase.
- 2026-05-25: P3 DONE — flattened client_manager nested error handling; scalarizer "nesting" was a false positive (sequential single-level trys). Committed.
- 2026-05-25: P9 DONE — mypy --strict 129→0 (5 parallel agents, type-only). Committed.
  Surfaced 3 mock-hidden latent bugs → logged as P10.
- 2026-05-25: P10 DONE — fixed action_fight body, trade seller→account, timeout wrap;
  updated the 3 tests that asserted the bugs. 0 type:ignore in those paths. Committed.
- 2026-05-25: P4 DONE — ApiActionError(code) replaces HTTP-string substring matching
  in player._execute; tests updated to raise the structured type. Committed.
- Next: P7 class-split (needs decision on enum/dataclass/SQLModel groupings),
  P5 C2 (~150 sites), P6 refactor god files, P8 cov→100.
- 2026-05-25: P7 DONE — split 8 behavioral multi-class files (13 new, 7 removed);
  AGENTS.md amended to exempt cohesive data/enum/Protocol groups. Committed.
- Next: P5 C2 (~150 sites, behavioral, per-site judgment), P6 refactor, P8 cov→100.
- 2026-05-25: P5a DONE — WorldState.from_character_schema raises MissingApiData
  (new) on absent/UNSET char stats instead of defaulting; +2 raise-path tests. Committed.
- Snapshot: 2246 pass / 0 warn / mypy 0 / ruff clean. 8 commits on fix/adversarial-review.
  Done: P1 P2 P3 P4 P5a P7 P9 P10.
- 2026-05-25: P5b DONE — utils/api_display.display_field + MISSING marker; routed
  display-only field access in all 7 command files through it (~115 sites); found
  another mock-hidden bug (bank details dict .get on attribute BankSchema). Committed.
- Snapshot: 2251 pass / 0 warn / mypy 0 / ruff clean. 9 commits.
  Done: P1 P2 P3 P4 P5a P5b P7 P9 P10.
  Remaining:
    * P6 — refactor god files info.py (1708) + player.py (1282). HIGH regression risk.
    * P8 — cover 274 lines (play.py 35%, helpers 80%, craft 93%) then enforce
      addopts: --cov=src/artifactsmmo_cli --cov-fail-under=100 --strict-markers -W error.
