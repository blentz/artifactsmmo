# PLAN: fight seconds learned from a fight's length (spec 2026-10-18 §2.9)

Rulings CA–CF (`.superpowers/sdd/2026-10-19-global-gear-objective-B/progress.md`
on the gear-plans worktree) are binding.

## Commit 1 — foundation (`feat(combat): record a fight's length; fit its seconds`)

- [x] `Cycle.fight_turns` / `Cycle.fight_haste` (nullable, not back-filled), migrated in place.
- [x] The recorder writes the server's `fight.turns` and the PRE-fight haste.
- [x] `WorldState.haste` from the character sheet.
- [x] `ai/fight_seconds_core.py`: `fight_seconds`, `fit` (least squares, h clamped at 0,
      cooldown <= 0 dropped from fit and floor, no observation raises).
- [x] `Formal.FightSeconds` (floor_le, mono_turns, anti_haste), oracle `fight_seconds`,
      `formal/diff/test_fight_seconds_diff.py`.
- [x] `learning/fight_seconds_model.py`: fleet store + `/my/logs` bootstrap fit, cache pinned
      to its store, learned action seconds (raise when unlearned), offline fit from
      `tests/test_ai/fixtures/fight_logs.json` (`scripts/capture_fight_logs.py`).
- [x] Mutants for the core and the adapter.

## Commit 2 — consumers (`feat(combat): a fight's seconds are learned from its length`)

- [ ] `SelectionContext.fight_seconds` / `action_seconds`; absent at use raises.
- [ ] Player and `plan` fill them (store fit + a one-page `/my/logs` bootstrap); offline
      worlds from the fixture via `shared_world` / scenarios / censuses.
- [ ] Expected turns: probability-weighted mean over `odds_walk` endings, capped at `MAX_TURNS`.
- [ ] Haste projected with the loadout (`project_loadout_stats`, `_wearing`, scenarios).
- [ ] Sites that time a SPECIFIC fight: `loop_rate`, `gear_objective._rate`/`_rated`,
      `rest_first`, `fight_loop_cost.loss_cost` + `rest_actions_per_fight`,
      `gold_per_second` (fighter in `L*(m*)`), `equip_cost` (its caller's monster).
- [ ] Action-unit sites: `make_seconds`, `strategic_weights`' fallback use the learned
      action seconds.
- [ ] Delete `FIGHT_SECONDS` / `TYPICAL_FIGHT_COOLDOWN_SECONDS`.
      `tiers/band_target.py` is dead (Plan C): left as is, noted. `bid_vs_craft`: docstring only.

## Then

- [ ] Re-apply `.superpowers/hotfix/zero-gain.patch`, full suite (`-n auto`), judge every
      moved outcome under §2.8/§2.9, commit `fix(objective): a piece that adds no XP is not missing`.
- [ ] Live `plan` for the five characters.
