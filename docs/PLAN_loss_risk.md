# PLAN: price a fight's loss risk

USER 2026-10-08, "Price the loss risk": a drop or grind fight's cost includes
its learned loss rate. Expected fights per win is `1/p`; each loss is charged
its death plus recovery.

## Evidence (learning.db, 2026-10-08)

- R2D2's `ReachSkill(jewelrycrafting->22)` grind fights `king_slime` (L15
  boss) for `king_slimeball`. At L30 in that loadout: 22 fights, 14 wins (64%).
  The veto (`WIN_RATE_THRESHOLD = 0.4`, `MIN_WIN_SAMPLES = 5`) does not fire.
- A loss ends at the respawn tile `(0,0)` with `hp = 1` (rows 411112, 411156).
  Recovery was 3x `UseConsumable` + `Rest` + `Withdraw(cooked_trout×3)` before
  the next fight.

## Where a fight is priced today

| Path | Losses priced? |
|---|---|
| `tiers/band_target` (character-XP grind) | YES: `LearningStore.fight_upkeep` counts every cycle per kill, losses included |
| `acquisition_cost._drop_actions` (DROP route) | NO: `kills × cycles_per_kill` (fight + forced rest) |
| `tiers/skill_grind_target` rung ranking | NO: prices rungs through `acquisition_actions(..., store=None)` inside a context-free cache |
| `drop_fight_selection.select_drop_fight` | NO, and stays so: proved expected-kills selector (`Formal.MonsterDropSelection`); one dropper per item in practice |

## Design

1. **Pure core `ai/loss_risk_core.py`**:
   `loss_surcharge(samples, wins, loss_cost) -> Fraction`, in fight-equivalents
   per WIN:
   - `samples < MIN_WIN_SAMPLES`: `0`. Same warmup as the veto; cold defers to
     the prediction.
   - `wins = 0`: `(samples) × loss_cost`. Total but unreachable in production,
     because the veto already refuses that fight.
   - otherwise `(samples - wins) / wins × loss_cost`, i.e. `(1/p - 1) × loss_cost`.
2. **`loss_cost(max_hp)`** in `learning/fight_loop_cost.py`: the lost Fight (1)
   plus a full-bar recovery, `rest_cooldown_seconds(max_hp, max_hp) /
   TYPICAL_FIGHT_COOLDOWN_SECONDS`. Rest is the policy-free recovery, the same
   reasoning the module gives for not pricing potions. The walk back from the
   respawn tile is a residual.
3. **Lean `Formal/LossRisk.lean`**: def mirrors the core over ℚ. Theorems:
   cold zero, lossless zero, `(1/p - 1)` identity for `wins > 0`, antitone in
   wins at fixed samples, monotone in `loss_cost`. Differential + mutants.
4. **The record reaches pricing through the context**:
   `SelectionContext.fight_records: tuple[tuple[str, int, int], ...]`, set as
   (monster, samples, wins) for each monster with a recorded loss at the
   current level, in its `fight_loadout`. `combat.fight_record` is the one
   reader; `is_winnable`'s veto calls it too. `_drop_actions` adds the
   surcharge per kill. The grind cache key gains `ctx.fight_records`, and the
   rung pricing passes them down.
5. **Witness**: a probe on a learning.db scratch copy. R2D2's
   jewelrycrafting rung price before and after; check whether the rung changes.

## Residuals

- Respawn walk-back is not priced.
- `cheapest_path_to_level` (projection) stays history-free.
