# PLAN: stat-computed protection tiebreak in the decide sort key

## Problem (trace 2026-06-17 23:45, Robby)

Empty `amulet_slot` and empty `body_armor_slot` both scored final=2.5, effort=3.
`EMPTY_SLOT_URGENCY` (`strategy.py:459`) saturates `max(marginal,1)*5/2` → both flatten
to exactly 2.5 regardless of the item's actual equip value. The sort key
`(-final, effort, repr)` then broke the tie **alphabetically**:
`air_and_water_amulet` < `feather_coat` → amulet chosen while the body slot sat empty.
Body armor (large hp_bonus) is strictly more protective; alphabet is an arbitrary
arbiter.

## Fix (user directive: calculable, not a hardcoded slot table)

Add a stat-computed tiebreak field to the proven decide sort key, ordered by the
EXISTING exact-int combat/utility metric `equip_value` (`tiers/equip_value.py`):

    protection(root) = max(0, equip_value(item) - equip_value(current_in_slot))   # empty slot ⇒ current=0

New key: `(-final, effort, -protection, repr)`. Higher protection sorts earlier
(negated, same convention as -final). `final` (the saturated 2.5 tier score) is
UNCHANGED — no rebalance ripple into GearPolicy/sticky-ratio; only the tiebreak
within an equal-(final,effort) collision gains a layer. feather_coat's hp_bonus
makes its equip_value delta exceed the amulet's small resistance delta → body
armor wins by computation. Non-gear / stats-None roots ⇒ protection 0.

## Touch list (formal lockstep — DecideKey.py ↔ DecideKey.lean ↔ Oracle ↔ Contracts ↔ Manifest ↔ diff)

1. `formal/Formal/DecideKey.lean` — add `negProtect : Int` to `Key`, insert
   `compareOn negProtect` between effort and rootRepr in `decideCmp`. Re-prove
   trichotomy/swap/lt_trans/eq_imp_{repr,negFinal,effort}; add new role
   `decideCmp_eq_imp_negProtect`. Update non-vacuity examples (4-field Key).
2. `formal/Formal/Manifest.lean` — add `decideCmp_eq_imp_negProtect` row.
3. `formal/Formal/Contracts.lean` — add exact-statement pin for the new role.
4. `formal/Oracle.lean::runDecideKey` — read protection args, build 4-field Key.
5. `src/.../tiers/decide_key.py` — `decide_key(neg_final, effort, neg_protection,
   root_repr)` → 4-tuple.
6. `src/.../tiers/strategy.py` — extract `_equip_gain(root,state,game_data)->int`
   (single source; `_marginal` reuses it); `decide()` passes `-protection`.
7. `formal/diff/test_decide_key_diff.py` — oracle call gains protection fields;
   `_expected_label` over 3-tuple; add protection-tiebreak case.
8. `tests/` — unit test: equal (final,effort), body armor (higher equip_value)
   outranks amulet via the live `StrategyEngine.decide`.

## Gate

`formal/gate.sh` full run (serialize — no concurrent src importers per
serialize-gate-runs memory). Then unit suite 100% cov.
