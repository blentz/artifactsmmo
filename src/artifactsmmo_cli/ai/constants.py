"""Shared numeric constants for the AI player subsystem."""

# Sliding window of recent cycles the StuckDetector inspects — wide enough to
# catch slow goal ping-pong loops without reacting to one-off retries.
STUCK_DETECTOR_WINDOW = 30

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
