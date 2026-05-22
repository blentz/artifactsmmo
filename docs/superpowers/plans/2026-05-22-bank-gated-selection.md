# Bank gated-selection + stale-lock fix

> Inline TDD. Tightly coupled (game_data → player → store); do not parallelize.

**Goal:** Stop the bot from latching onto an achievement-gated bank, mis-recording a global "bank locked, need L44" blocker, and permanently disabling all deposits while open banks exist.

**Live root cause:** 3 banks exist — (4,1) & (7,13) are `access:standard` (open), (-2,19) is `conditional` (needs `secure_the_island`). `game_data._load_maps` set `_bank_location` to the LAST bank tile seen with no access check, so it could pick the gated bank. Moving there returned HTTP 496 → the player recorded a global `bank` blocker (`sea_marauder`, L44) that persists in the learning DB and disables banking every session (Robby is L3, bank is actually empty 0/50).

**Architecture:** (A) `game_data` resolves `_bank_location` to an *open* bank (no access conditions), falling back to a gated one only if no open bank exists; exposes `has_open_bank()`. (B) `LearningStore.delete_blocker`; on blocker load the player drops a persisted `bank` lock when an open bank exists (the lock is bogus).

---

## Task 1: LearningStore.delete_blocker
- Add `delete_blocker(self, blocker_code)` mirroring `get_blocker` (get by code, delete if `character` matches), wrapped in the same `try/except SQLAlchemyError: pass`.
- Test: set_blocker → get_blocker not None → delete_blocker → get_blocker None.

## Task 2: game_data accessible-bank selection
- Add fields `_bank_location_open: bool = False`.
- Add staticmethod `_bank_tile_open(tile) -> bool`: True when `tile.access` is None/Unset, or its `conditions` is None/Unset/empty.
- In `_load_maps` BANK branch: if open → set `_bank_location=loc`, `_bank_location_open=True`; elif not already open → set `_bank_location=loc` (gated fallback).
- Add `has_open_bank(self) -> bool` → `self._bank_location_open`.
- Tests: tiles [gated(-2,19), open(4,1)] in either order → `_bank_location` is the open one, `has_open_bank()` True. Only-gated → picks gated, `has_open_bank()` False.

## Task 3: player drops stale bank lock when an open bank exists
- After `self._blockers = BlockerRegistry.load(..., known_codes=["bank"])` (player ~233):
  if `self.game_data.has_open_bank() and self._blockers.is_blocked("bank")`: `self._blockers.clear("bank")` and `self.history.delete_blocker("bank")` (guard history None).
- Test: seed a persisted bank blocker + game_data with an open bank; after load path, bank not blocked and store row gone. (Use a focused unit around the clear logic; full player init may need the existing player-test harness.)

## Task 4: clear Robby's live stale blocker
- One-off: the Task 3 logic clears it automatically on next run (open bank exists). No manual DB edit needed; note in summary.

## Task 5: verify
- `uv run pytest -q`; ruff + mypy on changed files; coverage parity.
