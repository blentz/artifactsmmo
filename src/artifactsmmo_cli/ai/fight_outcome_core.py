"""Pure core: a fight's expected-value outcome with in-fight restore potions
(`docs/PLAN_consumable_utility.md` increment 1; proved model
`formal/Formal/FightOutcome.lean`, differential
`formal/diff/test_fight_outcome_diff.py`).

The API's rule for a `restore` utility potion (game-data effect text): "Restores
X HP at the start of the turn if the player has lost more than 50% of their
health points" — every such turn, while stock lasts (increment 0: 1–7
`small_health_potion` consumed per fight).

The walk reads the closed form's terms (`fight_terms_core.FightTerms`) and works
in their exact ×10000 scale: the player's pool is `hp × 10000`, each monster
round removes `die_step`, and the fight is won in round `rounds_to_kill` (the
kill round is independent of the player's HP, so the walk counts rounds rather
than tracking the monster). At the start of each PLAYER turn, if
`max_hp × 10000 - pool > max_hp × 10000 / 2` — exactly `2 × pool < max_hp × 10000`,
no division — and stock remains, the pool gains `restore × 10000`, capped at
`max_hp × 10000`. With no stock the verdict is exactly `terms_win`
(`Formal.FightOutcome.fightOutcome_noStock_win`).

* `win` — the player kills the monster before its pool reaches 0;
* `turns` — the round the fight resolves in;
* `hp_end` — the player's pool at the end (×10000; 0 on a loss);
* `used` — restore potions drunk.

The guard exits of the closed form decide first: the out-sustain exit is a win
in `rounds_to_kill` rounds at the starting pool; every other exit is a loss in
round 0 (the fight is never walked). The turn cap needs no step of its own: the
kill round is at most `MAX_TURNS` past the `OVER_CAP` exit."""

from dataclasses import dataclass

from artifactsmmo_cli.ai.fight_terms_core import SCALE, FightExit, FightTerms, effective_player_hp


@dataclass(frozen=True)
class FightOutcome:
    """One fight's expected-value result (`hp_end` in the ×10000 scale)."""

    win: bool
    turns: int
    hp_end: int
    used: int


def _drink(pool: int, max_pool: int, restore_pool: int, stock: int) -> tuple[int, int]:
    """The restore rule at the start of a player turn: below half, drink one."""
    if 2 * pool < max_pool and stock > 0:
        return min(pool + restore_pool, max_pool), stock - 1
    return pool, stock


def fight_outcome(terms: FightTerms, hp_start: int, max_hp: int,
                  restore: int, stock: int) -> FightOutcome:
    """Walk the fight round by round from `hp_start` with `stock` restore potions
    of `restore` HP each (both non-negative)."""
    if restore < 0 or stock < 0:
        raise ValueError(f"restore {restore} and stock {stock} must be non-negative")
    max_pool = max_hp * SCALE
    pool = effective_player_hp(hp_start, max_hp) * SCALE
    if terms.exit is FightExit.OUT_SUSTAIN:
        return FightOutcome(True, terms.rounds_to_kill, pool, 0)
    if terms.exit not in (FightExit.NONE, FightExit.DEAD) or pool <= 0:
        return FightOutcome(False, 0, 0, 0)
    restore_pool = restore * SCALE
    left = stock
    for round_no in range(1, terms.rounds_to_kill + 1):
        if terms.player_first:
            pool, left = _drink(pool, max_pool, restore_pool, left)
            if round_no == terms.rounds_to_kill:
                return FightOutcome(True, round_no, pool, stock - left)
            pool -= terms.die_step
            if pool <= 0:
                return FightOutcome(False, round_no, 0, stock - left)
        else:
            pool -= terms.die_step
            if pool <= 0:
                return FightOutcome(False, round_no, 0, stock - left)
            pool, left = _drink(pool, max_pool, restore_pool, left)
            if round_no == terms.rounds_to_kill:
                return FightOutcome(True, round_no, pool, stock - left)
    return FightOutcome(True, 0, pool, 0)
