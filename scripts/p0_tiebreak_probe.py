"""P0 probe (docs/PLAN_no_alphabetical_tiebreak.md): replay the live arbiter for
Robby and print per-gear-root (final, effort, protection, owned_inputs) to test
whether gear roots ever TIE on the leading decide_key fields (final, effort,
protection). If they never tie, the decide_key repr tiebreak (Site B) is inert and
the load-bearing fix is sticky WIP-retention (Site C). Read-only, no actions.
"""
from fractions import Fraction

from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.ai.tiers.prerequisite_graph import objective_roots
from artifactsmmo_cli.ai.tiers.strategy import actionable_step, root_cost
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.owned_count import owned_count_pure


def owned_inputs(root, state, game_data):
    """Closeness-to-completion proxy: summed owned units of the root's direct
    recipe inputs, each capped at the required quantity."""
    if not isinstance(root, ObtainItem):
        return 0
    recipe = game_data.crafting_recipe(root.code)
    if recipe is None:
        return 0
    equipped = [c for c in state.equipment.values() if c is not None]
    total = 0
    for mat, qty in recipe.items():
        have = owned_count_pure(state.inventory, state.bank_items, equipped, mat)
        total += min(have, qty)
    return total


def main():
    config = Config.from_token_file()
    ClientManager().initialize(config)
    store = LearningStore(db_path=":memory:", character="Robby")
    store.start_session()
    try:
        player = GamePlayer(
            character="Robby", history=store,
            game_data_ttl_minutes=config.game_data_ttl_minutes,
        )
        report = player.plan_once()
        state = player.state
        gd = player.game_data
        engine = player._strategy
        print(f"chosen_root={report.decision.chosen_root}  "
              f"chosen_step={report.decision.chosen_step}")
        print("=" * 96)
        print(f"{'root':<52}{'final':>10}{'effort':>8}{'protect':>9}{'owned_in':>9}")
        rows = []
        for root in objective_roots(engine.objective, state):
            if root.is_satisfied(state, gd):
                continue
            value = engine._value(root, state, gd, None, store)
            final = engine._learned_blend(root, value, store, None)
            effort = root_cost(root, state, gd)
            protection = engine._equip_gain(root, state, gd, store)
            oin = owned_inputs(root, state, gd)
            rows.append((repr(root), float(final), effort, protection, oin,
                         (round(float(final), 6), effort, protection)))
        rows.sort(key=lambda r: (-r[1], r[2], -r[3]))
        for rp, final, effort, prot, oin, _lead in rows:
            print(f"{rp[:52]:<52}{final:>10.4f}{effort:>8}{prot:>9}{oin:>9}")
        # tie detection on leading (final, effort, protection)
        from collections import Counter
        leads = Counter(r[5] for r in rows)
        ties = {k: v for k, v in leads.items() if v > 1}
        print("=" * 96)
        if ties:
            print(f"LEADING-FIELD TIES FOUND (repr tiebreak WOULD fire): {ties}")
        else:
            print("NO leading-field ties among roots -> decide_key repr field is INERT this state")
    finally:
        store.end_session(exit_reason="normal")
        store.close()


if __name__ == "__main__":
    main()
