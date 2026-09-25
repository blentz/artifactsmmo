# PLAN: fleet-wide rate governor + fleet-cached account reads

Status: implemented (2026-09-25); live witness pending.

## Problem

Live 2026-09-25 03:14Z: Lor, R2D2 and Robby recorded no cycle for 18-19 minutes.
`py-spy` showed each one blocked in `_acquire_account` -> `RateGovernor.acquire`.

- `/my/rates` declares the account bucket at 300/hour per IP. `MultiRun.build_pool`
  divides it statically (`split_budget`), so each of the 5 children gets 60/hour.
- `_reconcile_open_orders` calls `/my/grandexchange/orders` (account bucket) on
  EVERY cycle. At ~45-50 cycles/hour, that alone spends most of a child's 60/hour,
  and bank/pending syncs spend the rest. Once the hourly window is full, the
  child sleeps until it rolls over.
- `/my/grandexchange/orders`, `/my/bank`, `/my/bank/items` and `/my/pending_items`
  are ACCOUNT-scoped: every child reads the same answer, five times over.
- The static split also wastes budget: an idle child's share cannot be used by a
  busy one.

## Design (user-approved choices)

1. **One fleet-wide governor per bucket (account, data, action).**
   `RateGovernor`'s request history moves from an in-process deque into a
   `rate_requests` table in the shared coordination DB. `RequestLog.try_record`
   counts the windows and inserts the new row inside one `BEGIN IMMEDIATE`
   transaction, so the check-and-record is atomic across processes. Children get
   the UNDIVIDED budget.
   - Planner pricing is unchanged: `sustainable_interval()` still reports the
     per-child fair share, `budget.divided_by(sharers)`, as before.
   - The clock is `time.monotonic` (CLOCK_MONOTONIC is system-wide on Linux), so
     timestamps written by different processes are comparable.
2. **Fleet cache for account-scoped reads** (`AccountReadCache`, table
   `account_reads`). The keys are `ge_open_orders`, `bank` and `pending_items`.
   - TTL is DERIVED from the budget:
     `ttl(key) = cost(key) * len(KEYS) * account_interval / IDLE_SHARE`.
     `cost` is the number of requests the key's last fetch actually made, and
     `account_interval` is the FULL account bucket's sustainable interval.
     Idle refreshes of all keys together can then spend at most `IDLE_SHARE`
     (1/2) of the account bucket. The other half is left for forced reads.
   - Single-flight: when a key goes stale, one process takes a refresh lease and
     the others serve the stale value until it publishes.
   - A process that just MUTATED the resource (a bank action, a GE cancel or
     post, a pending claim) reads with `force=True`, which fetches and
     publishes, so siblings see its change immediately.
3. A lone `play <character>` (no coordination DB) keeps its current behaviour:
   no governor and no cache.

## Steps

- [x] `RequestLog` + `RateGovernor` backed by it; delete `split_budget`
- [x] `play.py` / `MultiRun`: pass the full budget + `--fleet-size`; build the shared governors
- [x] `AccountReadCache` + wire `_fetch_open_orders`, `_sync_bank`, `_sync_pending`
- [x] GE-order dirty flag after own GE cancel/post
- [ ] Tests (done), gate (green except the pre-existing `test_ladder_fires_diff` oracle timeout, which `main` 06981b00 reproduces), live witness (cycles/hour, no `_acquire_account` stalls)
