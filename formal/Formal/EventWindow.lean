-- @concept: events @property: totality, safety, dominance, monotonicity, reachability
/-
Formal model of the pure event-NPC trade-window gate extracted from
`src/artifactsmmo_cli/ai/event_availability.py` (`event_npc_tradeable`).

A non-event NPC is ALWAYS tradeable here (the caller's other checks — location
known, price, gold/inventory — still apply). An EVENT NPC is tradeable only when
its event is active AND the spawn is known AND the event window will NOT expire
before the character can walk to the spawn tile (with a fixed safety margin):

    BUY-window-open  iff  remaining > travel + margin

where the Python core computes
  `travel_seconds = distance * EVENT_TRAVEL_SECONDS_PER_TILE` (5.0/tile),
  `remaining = (expiration - now).total_seconds()`, and the margin is
  `EVENT_ARRIVAL_MARGIN_SECONDS` (10.0), returning
  `remaining > travel_seconds + EVENT_ARRIVAL_MARGIN_SECONDS`.

This mirrors that decision exactly over `Int` (the comparison is decidable; the
model ranges over all integers — `remaining` can be negative when the event has
already expired).

FLOAT → INT FAITHFULNESS NOTE.
  The Python constants are floats (`5.0` per tile, `10.0` margin), but both are
  exact integers in IEEE-754 double, and the Manhattan `distance` is an integer,
  so `distance * 5.0` is exactly representable and equals the integer
  `distance * 5`; likewise `margin = 10.0` equals the integer `10`, and
  `remaining` is fed to the differential as `int((expiration-now).total_seconds())`.
  The only operation is a single `>` comparison of these exact values, so the
  boolean the float code computes is IDENTICAL to the one this `Int` model
  computes — there is no rounding step between the inputs and the comparison.
  (The differential drives the LIVE Python function and feeds the oracle the same
  six integers, so this faithfulness is mechanically checked, not just asserted.)

Lean core only — no mathlib. `decide`/`split`/`simp only [eventNpcTradeable]`/
`omega` close every goal; same core-only convention as `Formal/CraftVsBuy.lean`.

OUT OF SCOPE (remaining future work): event-SPAWNED combat/resource content
(special maps/monsters that appear only while an event is live) is not modeled
here — this gate covers only the event-NPC TRADE window.
-/

namespace Formal.EventWindow

/-- True iff an event NPC can be traded with right now, given:
* `isEvent`  — the NPC is event-gated (Python: `npc_event_code is not None`),
* `active`   — its event is currently active (Python: code ∈ `active_events`),
* `hasSpawn` — the spawn tile is known (Python: `npc_location is not None`),
* `remaining` — seconds left on the event window (`(expiration - now)`),
* `travel`    — travel seconds to the spawn (`distance * 5`),
* `margin`    — arrival safety margin (`10`).

Mirrors `event_npc_tradeable`: a non-event NPC is unconditionally tradeable; an
event NPC needs an active event, a known spawn, and a window that outlasts
`travel + margin`. -/
def eventNpcTradeable (isEvent active hasSpawn : Bool) (remaining travel margin : Int) : Bool :=
  if not isEvent then true
  else if not active then false
  else if not hasSpawn then false
  else decide (remaining > travel + margin)

/-- TOTALITY: the gate is always exactly `true` or `false` (no third outcome,
no stuck state). Trivial for `Bool`, but pinned as the honest totality witness. -/
theorem tradeable_total (isEvent active hasSpawn : Bool) (r t m : Int) :
    eventNpcTradeable isEvent active hasSpawn r t m = true ∨
    eventNpcTradeable isEvent active hasSpawn r t m = false := by
  cases eventNpcTradeable isEvent active hasSpawn r t m
  · exact Or.inr rfl
  · exact Or.inl rfl

/-- DOMINANCE (non-event short-circuit): a NON-event NPC is ALWAYS tradeable here,
regardless of every other input (matches the Python `return True` on
`event_code is None`). -/
theorem non_event_always_tradeable (active hasSpawn : Bool) (r t m : Int) :
    eventNpcTradeable false active hasSpawn r t m = true := by
  simp only [eventNpcTradeable, Bool.not_false, if_true]

/-- SAFETY (inactive event): an event NPC whose event is NOT active is never
tradeable (Python `return False` on `expiration is None`). -/
theorem inactive_event_not_tradeable (hasSpawn : Bool) (r t m : Int) :
    eventNpcTradeable true false hasSpawn r t m = false := by
  simp only [eventNpcTradeable, Bool.not_true, Bool.not_false, if_true]
  decide

/-- SAFETY (unreachable window): an active, spawned event whose REMAINING time
does not strictly exceed `travel + margin` is never tradeable — the bot refuses
to start a trip the window cannot outlast (Python's `remaining > travel + margin`
is false). -/
theorem unreachable_window_not_tradeable (r t m : Int) (h : r ≤ t + m) :
    eventNpcTradeable true true true r t m = false := by
  simp only [eventNpcTradeable, Bool.not_true]
  exact decide_eq_false (by omega)

/-- DOMINANCE (exact firing condition): for an active, spawned event the gate is
`true` IFF the window strictly outlasts `travel + margin` — the precise reachable
condition, with no over- or under-firing. -/
theorem tradeable_iff_window_open (r t m : Int) :
    eventNpcTradeable true true true r t m = true ↔ r > t + m := by
  simp only [eventNpcTradeable, Bool.not_true]
  exact decide_eq_true_iff

/-- MONOTONICITY in remaining: once the gate fires, GROWING the remaining window
keeps it open (more time never closes a reachable window). -/
theorem tradeable_monotone_in_remaining (r r' t m : Int)
    (h : eventNpcTradeable true true true r t m = true) (hle : r ≤ r') :
    eventNpcTradeable true true true r' t m = true := by
  rw [tradeable_iff_window_open] at h ⊢
  omega

/-- MONOTONICITY (antitone in distance): once the gate fires, SHRINKING the travel
cost keeps it open (a nearer spawn is at least as reachable). -/
theorem tradeable_antitone_in_distance (r t t' m : Int)
    (h : eventNpcTradeable true true true r t m = true) (hle : t' ≤ t) :
    eventNpcTradeable true true true r t' m = true := by
  rw [tradeable_iff_window_open] at h ⊢
  omega

/-- REACHABILITY (anti-vacuity true-branch witness): there EXISTS an active,
spawned event with a non-negative travel cost and non-negative margin for which
the gate genuinely fires. This proves the `true` branch is reachable under the
real input invariants (`travel ≥ 0`, `margin ≥ 0`), so none of the theorems above
are vacuously about an empty case. -/
theorem window_open_reachable :
    ∃ (r t m : Int), eventNpcTradeable true true true r t m = true ∧ t ≥ 0 ∧ m ≥ 0 := by
  refine ⟨11, 0, 10, ?_, ?_, ?_⟩
  · rw [tradeable_iff_window_open]; omega
  · omega
  · omega

end Formal.EventWindow
