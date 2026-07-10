# Fight-Loadout Precondition — Design

Date: 2026-07-10
Status: approved (design); implementation via phased plan
Relates to: [[project_slot_exhaustion_livelock]] (the enabling condition), [[project_combat_veto_threshold]], [[feedback_no_predict_win_in_goap_precondition]]

## Problem

The AI player loses fights it should win because it fights with the WRONG
loadout equipped. Confirmed live (character Robby, L13): fighting cows (the
lowest monster) with a `copper_pickaxe` (mining tool, 5 attack) in the weapon
slot instead of his owned `water_bow`, ending fights at 1-5 HP — a coin-flip
that should be trivial.

Root cause (verified end-to-end):
1. Gathering equips a tool (`OptimizeLoadout(gather:mining)` → pickaxe). Nothing
   swaps it back to a weapon until a fight forces it.
2. `pick_loadout(Combat(cow))` correctly picks `water_bow` — a 1-slot swap
   (`weapon_slot: pickaxe → water_bow`).
3. That swap displaces the pickaxe → needs 1 free slot. At a full bag
   (`inventory_slots_free==0`), `OptimizeLoadout(combat).is_applicable` is False
   (the just-shipped slot gate) — the swap cannot execute.
4. `is_winnable(cow)` is True — it correctly evaluates the BEST on-hand loadout
   (`combat.py:152` uses `pick_loadout_cached`), so the bot commits to the
   fight believing it has `water_bow`…
5. …but execution uses the EQUIPPED pickaxe (5 attack) → marginal → `fight_lost`.

Today `FightAction` only SOFT-penalizes a suboptimal loadout (`LOADOUT_PENALTY`
in `cost`, `combat.py:141`), sequencing `OptimizeLoadout(combat)` before the
fight WHEN it can. When the swap is slot-blocked (or the penalty is
outweighed), the planner fights bare. The gap: `is_winnable` COMMITS on the
best loadout, but EXECUTION uses whatever is equipped.

## What this fixes

The bot must never fight with a loadout materially worse than its best
on-hand combat loadout. A hard precondition forces the loadout swap (and, when
the bag is full, the slot-relief that unblocks the swap) to run BEFORE the
fight.

## Approach (selected: A — hard optimal-loadout precondition)

`FightAction.is_applicable` gains a hard requirement: the equipped loadout must
match the optimal combat loadout for the target monster. When it does not, the
fight is not applicable, so the GOAP planner is forced to sequence
`OptimizeLoadout(combat)` first (which, at a full bag, is itself gated on slot
room, so relief runs first — the chain `relief → OptimizeLoadout(weapon) →
Fight`).

Rejected:
- B (winnability-with-equipped gate): precise but leaves "fight with a
  slightly-suboptimal but still-winning loadout" — the bot should always fight
  with its BEST loadout, not merely a winning one.
- C (strengthen the soft penalty only): does not fundamentally prevent
  fighting bare when the swap is blocked.

Why A is safe (not over-constraining, no livelock): `pick_loadout` returns the
best loadout from OWNED items (inventory + equipped) and is REALIZABLE
(`equipment/realizable_loadout.py` — every chosen code is physically providable),
so `OptimizeLoadout(combat)` can always reach it (given slot room, freed by
relief). After the swap, equipped == optimal → the fight is applicable. The
extra `OptimizeLoadout` step only ever fires when equipped ≠ optimal — exactly
the case we want it.

## Components

### 1. Shared loadout-match predicate

A pure helper (extract from the existing `FightAction.cost` comparison):

```
def equipped_matches_loadout(equipment, optimal) -> bool:
    # optimal only carries the slots it fills; match per-slot (equipment
    # carries only filled slots, so direct dict-eq disagrees on shape).
    return not any(equipment.get(slot) != code for slot, code in optimal.items())
```

Consumed by BOTH `FightAction.cost` (drop `LOADOUT_PENALTY` in favor of the
hard gate, OR keep the penalty as a tie-break for the swap ordering — decided
in the plan) and `FightAction.is_applicable` (the new hard gate). One locus,
no divergence.

### 2. `FightAction.is_applicable` hard gate

Append to the existing structural gates (locations, inventory room, HP floor,
xp-positive/drop-farm, level+2 suicide guard, is_winnable): the equipped
loadout must match `pick_loadout_cached(Combat(monster_attack, monster_
resistance), state, game_data)`. When it does not, return False.

The `pick_loadout` call is already memoized (`pick_loadout_cached`) — no new
CPU cost beyond what `cost` already pays each node.

### 3. Interaction with the slot-relief (already shipped)

No new slot code. `OptimizeLoadout(combat).is_applicable` is already slot-gated
(displaced items need free slots); at a full bag the deposit/relief ladder
(`deposit_inventory` / `inventory_caps`, slots-full-aware) frees a slot first.
The planner composes `relief → OptimizeLoadout(combat) → Fight`.

### 4. Formal-layer: liveness / no-deadlock (the delicate part)

`FightAction.is_applicable` participates in the liveness proofs
(`ai_reaches_fifty*`, `test_no_deadlock`, GrindLadder / MonsterDropApply
liveness). The hard loadout precondition means a fight now has `OptimizeLoadout
(combat)` as a bounded predecessor. The implementation MUST show:
- The `no_deadlock` scenarios still hold (a fight goal from a tool-equipped
  state still produces a directional plan: swap-then-fight, not a stall).
- The liveness narrative is preserved: `OptimizeLoadout(combat)` terminates and
  reaches the required loadout (realizable), so the fight becomes applicable —
  no cycle, no new unsatisfiable hypothesis.
- `fightApplicable` in `ActionApplicability.lean` is an UNBOUND sketch (not
  diff-bound — verified during the slot work), so there is no differential
  lockstep to update for the Python gate. BUT if any liveness proof references
  fight applicability in a way the new gate changes, that proof must be
  re-examined ([[feedback_zero_vacuousness]], [[project_grind_liveness_proven]]).

### 5. Fight-for-drop full-bag deadlock (secondary)

`GatherMaterials(cowhide)` returns an empty plan at a full bag (verified, 30s
budget). This is a related but possibly distinct symptom (fight-for-drop needs
the weapon-swap slot AND drop room). During implementation, CONFIRM whether the
hard-gate + relief sequencing resolves it (the plan becomes `relief → swap →
fight`). If it remains a deadlock, root-cause it separately and either fix (if
in the same slot-contention family) or file a follow-up — it is NOT allowed to
silently stay a deadlock without a decision.

## Data flow

```
FightAction.is_applicable(state):
  ... existing structural gates + is_winnable(best loadout) ...
  optimal = pick_loadout_cached(Combat(monster), state, game_data)
  if not equipped_matches_loadout(state.equipment, optimal): return False
  -> planner cannot Fight until equipped == optimal
  -> sequences OptimizeLoadout(combat) (slot-gated -> relief frees slots when full)
  -> after swap, equipped == optimal -> Fight applicable -> fights with best loadout
```

## Error handling

- Use only game data. `pick_loadout` already fails loudly on missing data; no
  new defaulting.
- No new exception handling; never catch Exception.
- One predicate (`equipped_matches_loadout`) shared by cost + is_applicable —
  no multi-locus loadout logic.

## Testing

- Unit: `equipped_matches_loadout` (match / per-slot mismatch / optimal-subset).
- Applicability: a tool-equipped state where the optimal loadout differs →
  `FightAction.is_applicable` False; an already-optimal state → True.
- Scenario (offline planner): a tool-equipped + weapon-owned state where a fight
  is needed → the plan sequences `OptimizeLoadout(combat)` (equip the weapon)
  BEFORE `Fight`; the full-bag variant → `relief → swap → fight`; an
  already-optimal state → `Fight` with no extra swap.
- no_deadlock: the pinned scenarios stay green (fight goals still produce
  directional plans); add a tool-equipped-fight scenario proving swap-then-fight.
- Lean: `lake build` clean; liveness/no-deadlock proofs re-verified (the fight
  predecessor is bounded); no new axioms.
- Runtime (mandatory, [[feedback_verify_runtime_activation]]): live Robby — a
  cow fight now equips `water_bow` (not the pickaxe) before fighting; the
  fight is won.
- Full gate (`formal/gate.sh`) green, serialized (bot down).

## Scope / non-goals

- NOT changing `is_winnable`/`pick_loadout` (they are correct — best-on-hand).
- NOT re-tuning `LOADOUT_PENALTY` values beyond the cost/gate refactor.
- The fight-for-drop deadlock is a CONFIRM-or-follow-up, not core.
- The cow's low base stats / gear progression are unrelated (out of scope).

## Risks

- Liveness proof breakage: the hard gate adds a fight predecessor; the reach-50
  / grind-ladder liveness must be re-verified. Highest-attention item.
- Over-gating: if `pick_loadout` ever returns an unrealizable loadout, the fight
  would be permanently blocked (livelock). Mitigated by the realizable-loadout
  invariant (already proven); add a scenario asserting swap-reaches-optimal.
- Plan-shape churn: many fight plans now front-load `OptimizeLoadout` when not
  optimal — re-derive affected scenario goldens as genuine improvements (the
  bot now fights better-equipped), not regressions.
