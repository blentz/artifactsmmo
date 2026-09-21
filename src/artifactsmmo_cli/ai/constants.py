"""Shared numeric constants for the AI player subsystem."""

# Sliding window of recent cycles the StuckDetector inspects — wide enough to
# catch slow goal ping-pong loops without reacting to one-off retries.
STUCK_DETECTOR_WINDOW = 30

# EXPONENTIAL backoff after an action that FAILED while leaving no server
# cooldown, so a persistent error (e.g. a Withdraw that keeps returning HTTP 478)
# cannot spin the cycle loop at full CPU. The delay doubles per consecutive
# no-cooldown failure (BASE, 2*BASE, 4*BASE, …) up to MAX, then resets to 0 on
# the next successful (or cooldown-only) cycle — fast to recover from a one-off
# error, but quickly idle on a true livelock.
ERROR_BACKOFF_BASE_SECONDS = 1.0
ERROR_BACKOFF_MAX_SECONDS = 60.0

# Force a full state refresh (character + bank + pending items) after this
# many successful actions, so the lazily-loaded bank_items never stays stale
# for long (ALL bank-aware planning is inert while bank_items is None/stale).
BANK_REFRESH_INTERVAL = 20

# Sentinel seeded into the refresh counter at startup: any value at or above
# BANK_REFRESH_INTERVAL forces the cycle-0 full refresh that loads bank_items
# BEFORE the first plan, instead of ~20 cycles later.
BANK_REFRESH_FORCE_SENTINEL = 9999

# Game API error code 499 ("Character in cooldown"): the action was rejected
# because the previous action's cooldown has not expired yet.
ERROR_CODE_COOLDOWN = 499

# Game API error code 485 ("This item is already equipped"): the equip
# endpoint rejected the item because the same item code is already worn in
# another slot. EquipAction.is_applicable gates this at plan time, so a planned
# equip should never 485 — but when the occupancy MODEL behind that gate is
# wrong it does, and then it does so forever (2026-06-10 Robby utility2;
# 2026-08-22 Lor artifact2/3, 55 cycles in 50 minutes). It stays an ordinary
# failed-cycle outcome AND is a CATEGORICAL rejection: see
# ai/action_rejection.py, which bounds the loop even while the model is wrong.
ERROR_CODE_ALREADY_EQUIPPED = 485

# Game API error code 404 ("Order not found") on a Grand Exchange fill: the
# standing order our index named has been filled or cancelled by another
# account. The order book is read ONCE at startup, so nothing else ever retires
# a consumed order — and the planner re-derives the identical impossible fill
# every cycle at cooldown 0.0, free-spinning against the per-IP budget (live
# 2026-09-21 Robby: 64 of 424 cycles on one dead sunflower order, in seven
# bursts over eight hours). NOT a categorical rejection: it is a fact about one
# order id, not about the item, and `ai/action_rejection.py` keys on
# (class, item code) — poisoning there would wall the item for the session.
ERROR_CODE_ORDER_NOT_FOUND = 404

# Game API error code 434 ("This offer does not contain that many items") on a
# Grand Exchange fill: the PARTIAL twin of 404 above. The order still stands —
# other accounts have merely drained it below the quantity our index recorded.
# Every build site gates the ask on that cached quantity (`craft_ladder`'s
# `order[2] < qty`, and the same test in goals/gathering and goals/progression)
# and none of them clamps it, so a 434 can only mean the cached number is
# wrong. Because the order id stays valid the 404 hook never fires, and the
# stale quantity ages for the whole run.
#
# Live 2026-09-21 (Robby): order 6ab0c9cdc215f6bd0f9d7912 was down to 2 units
# while Robby asked it for 51, 24, 12, 6, 6, 6 — at cooldown 0.0, and with 46
# units standing in a sibling order at the same price the whole time.
ERROR_CODE_OFFER_SHORT = 434

# How long the Grand Exchange order index may stand before the run re-reads the
# whole book. Retiring a ghost on its own 404 (ERROR_CODE_ORDER_NOT_FOUND above)
# only ever SHRINKS the index; an order posted by another account after startup
# stayed invisible for the rest of the run, so a route the book could supply was
# priced as though no order existed. Only a periodic re-read makes the index
# grow again.
#
# Cost, measured against the live book 2026-09-21: 32 buy orders on 1 page and
# 1575 sell orders on 16, so 17 requests per reload and 68 per hour per
# character at this interval. `/grandexchange/orders` answers
# `x-ratelimit-limit-hour: 2000`, which is the DATA bucket (the account bucket
# is 300) — about 17% of one child's divided data share at five children, and
# charged through `_acquire_data` rather than taken for free.
GE_ORDER_REFRESH_INTERVAL_SECONDS = 900.0

# Standard HTTP 429 ("Too Many Requests"): the per-IP throttle `play --all`
# children divide between themselves as a soft budget (see utils/rate_governor.py)
# tripped anyway. Undocumented in the OpenAPI spec this project's client is
# generated from, so it never becomes an ErrorResponseSchema/ApiActionError —
# detected instead via a raw httpx response hook
# (rate_limit_detector.detect_rate_limited_response, wired in client_manager.py)
# that raises RateLimitedError before the generated client's `_parse_response`
# can discard the status code. See GamePlayer.is_rate_limited/RATE_LIMITED_OUTCOME.
ERROR_CODE_RATE_LIMITED = 429
