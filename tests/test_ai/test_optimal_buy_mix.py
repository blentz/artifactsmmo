from artifactsmmo_cli.ai.optimal_buy_mix import optimal_buy_mix_pure


def test_buys_up_to_affordable_batch():
    # need [1,1], held [0,0], price [2,3] -> cost(B)=5B; gold=12 -> B=2 (cost 10<=12), B=3 cost15>12
    assert optimal_buy_mix_pure([1, 1], [0, 0], [2, 3], 12, 100) == 2


def test_held_reduces_cost():
    # held covers part: need[1], held[5], price[2]; cost(B)=2*max(0,B-5); gold=4 -> B up to 7 (cost 4)
    assert optimal_buy_mix_pure([1], [5], [2], 4, 100) == 7


def test_capped_at_max_batch():
    assert optimal_buy_mix_pure([1], [100], [2], 1000, 5) == 5  # held>=need*B for B<=5; capped


def test_zero_gold_only_what_is_covered():
    # gold 0 -> can only make batches fully covered by held: need[2] held[6] -> B=3
    assert optimal_buy_mix_pure([2], [6], [5], 0, 100) == 3


def test_zero_when_first_batch_unaffordable():
    # cost(1) = 2*5 = 10 > gold 3, and held covers nothing -> best stays 0
    assert optimal_buy_mix_pure([5], [0], [2], 3, 100) == 0


def test_multi_ingredient_scarcest_priced_caps():
    # need [2,1], held [0,0], price [3,1]; cost(B)=6B+B=7B; gold=20 -> B=2 (14<=20), B=3=21>20
    assert optimal_buy_mix_pure([2, 1], [0, 0], [3, 1], 20, 100) == 2
