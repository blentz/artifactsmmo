# Multi-Character Support — Known Follow-Ups

Recorded 2026-07-31 at the close of the `play --all` epic (`c913b4c4..5fc87acd`).
Everything here was found during implementation or review, judged non-blocking,
and deliberately NOT fixed. None of it blocks merge. Listed so it is not lost.

## Rate-governor coverage gaps (same class, different files)

The account bucket is the tightest limit at **300/hour** — 60/hour/child at five
children. Three outbound account-scoped reads still charge no governor:

- `ai/actions/claim.py:61` — `get_pending_items`, tagged `"My account"` in
  `openapi.json`. Reached through action dispatch, which charges the *action*
  governor, so this read is counted against the wrong bucket.
- `ai/game_data.py:1441` — `get_bank_details`, account-scoped, ungoverned.
- `ai/game_data.py:1462` — `get_account_details`, account-scoped, ungoverned.

The last two run at startup only, so five children cost ten uncounted account
requests per launch against a 300/hour ceiling — real but small.

**The bucket→endpoint mapping itself is an inference.** It comes from reading
`openapi.json` tags (`"My account"` → account, `"Characters"`/`"Achievements"`
→ data, `/my/{name}/action/*` → action) against the rate-limit doc's wording.
It has never been calibrated against the live `remaining` counters that
`/my/rates` returns. **Do one live calibration run at five characters before
trusting it** — `/my/rates` reports `limit`, `remaining`, and `reset` per
bucket per window, so a short run comparing observed decrements against
predicted ones would settle it definitively.

## Supervisor lifecycle

- `asyncio.gather` in `CharacterSupervisor._run_once` does not cancel the
  sibling reader when one raises, leaving a short-lived orphan `_read_stderr`
  task until the process is reaped.
- `WatchApp.update_snapshot` now returns early when the app is not running,
  which also skips `self._store.record(snap)`. Snapshots arriving before mount
  are dropped rather than buffered. Previously they were recorded and then
  crashed on `query_one`, so this is strictly better, but it is a behaviour
  choice worth revisiting if early snapshots ever matter.
- `CharacterSupervisor` keeps only the FIRST exit event if a child emits two
  (`reason_box[0]`), with no diagnostic. The protocol emits exactly one, so this
  is inert unless a child misbehaves.

## Rate-budget headroom

`tests/test_ai/test_rate_budget_headroom.py` assumes **one page per global-read
refresh** for `_fetch_active_events` / `_fetch_raids` (page size 100). Real
headroom is 1390 vs the 2000/hour data ceiling, but the doubled-refresh case
the docstring cites computes to 1990 — only ten requests of slack. A *third*
page per refresh would breach. Safe while live event/raid counts stay in the
single digits to low tens; revisit if that changes.

## Minor / inert

- `WindowBudget.divided_by` is public but has no `children <= 0` guard of its
  own, relying on `split_budget`'s validation. A direct call with `0` raises
  `ZeroDivisionError` rather than the project's `ValueError` convention.
- `GamePlayer.is_rate_limited` has no production caller — dispatch is by
  exception type, not by integer code. Kept as a tested, centralised classifier
  rather than inventing an artificial call site.
- `MapPane.set_others` clears the entire `_line_cache` rather than only the
  affected rows. The signature mechanism alone would catch staleness, so this
  is redundant work on every foreign-character update. Latent perf only.

## Deliberately out of scope (design decision, not a defect)

No coordination between characters: no bank leases, no shared planning, no
division of labour. Five independent AIs race the same bank, recovering via the
existing `ApiActionError` → `error:*` → replan path. **Whether that thrash is
acceptable in practice is the open question this epic could not answer without
live traces** — it is the motivating data for any future coordination work.
Check the traces after a multi-character run before designing collaboration.
