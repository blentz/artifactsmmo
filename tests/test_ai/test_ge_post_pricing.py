from artifactsmmo_cli.ai.ge_post_pricing import sell_post_price, buy_post_price


class TestSellPostPrice:
    def test_no_anchor_returns_none(self):
        assert sell_post_price(None, npc_sellback=5, margin=1) is None

    def test_undercuts_best_sell_by_one_tick(self):
        assert sell_post_price(best_sell=20, npc_sellback=5, margin=1) == 19

    def test_floored_at_npc_sellback_plus_margin(self):
        # best_sell-1 = 5 would sit below the floor 6; clamp up to the floor.
        assert sell_post_price(best_sell=6, npc_sellback=5, margin=1) == 6


class TestBuyPostPrice:
    def test_no_anchor_returns_none(self):
        assert buy_post_price(None, alt_cost=15, margin=1) is None

    def test_overbids_best_buy_by_one_tick(self):
        assert buy_post_price(best_buy=8, alt_cost=15, margin=1) == 9

    def test_ceilinged_at_alt_cost_minus_margin(self):
        # best_buy+1 = 15 would sit above the ceiling 14; clamp down to the ceiling.
        assert buy_post_price(best_buy=14, alt_cost=15, margin=1) == 14
