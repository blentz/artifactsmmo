"""Shared analysis of currency-buy leaves in a recipe closure.

A "currency-buy leaf" is a closure member (a recipe input OR the requested
item itself) that can ONLY be acquired by buying it from an NPC against a
currency (e.g. jasper_crystal @ tasks_trader for 8 tasks_coin). Such a leaf:
  - has no crafting recipe,
  - is not a resource drop,
  - is dropped by no monster,
  - is sold by at least one NPC (npc_purchases non-empty).

A leaf is AFFORDABLE when some PERMANENT, located vendor offers it at a currency
price the character can cover (>= price * closure_qty). An ITEM currency pays
from inventory + bank stacks of that item; GOLD pays from `state.gold` plus
KNOWN bank gold (`state.bank_gold or 0` — an unknown bank credits nothing,
GAP-1's bank-stock rule). Gold is NOT an inventory item: reading
`inventory["gold"]` scored every gold price as unaffordable no matter how much
gold the character held, which pruned every gold-priced vendor purchase at
is_plannable (GAP-3, l30_rune_fill: 25000 gold in hand, the 20000 lifesteal_rune
one buy away, cycle Waits). Event/unlocated vendors are excluded —
`relevant_actions` emits no NpcBuy for them, so they must not count as a usable
purchase path (closure + vendor set kept symmetric with
GatherMaterialsGoal.relevant_actions).

GOLD-RESERVE DISCIPLINE (follow-up wave Task 3, 2026-07-08): a gold-priced leaf
must ALSO clear the same progression-reserve floor BANK_EXPAND protects
(`progression_reserve.reserve_floor`), so a discretionary vendor buy never eats
the gold set aside for near-term gear. Invariant: POST-BUY TOTAL GOLD (pocket +
bank) >= reserve, i.e. `gold_on_hand >= price * qty + reserve` (P4a exact-int
form, no signed subtraction — mirrors `progression_reserve_core.affordable`).
`reserve` is `reserve_floor(state, game_data, leaf)`: buying a leaf that is
ITSELF a reserved near-term target fulfills that reservation, so
`effective_floor` deducts the leaf's own entry before applying the floor — a
leaf is never blocked by its own reservation, only by OTHER unmet targets.
Item-currency legs are untouched: the reserve is gold-denominated only.
Threading: `analyze_currency_leaves` already receives `state`/`game_data`, so
`progression_reserve.reserve_floor` is called directly here — `ai/goals/` does
NOT participate in the `tiers/means.py` import cycle (that cycle is specific to
`tiers/means.py` importing back into the `tiers` package via
`progression_reserve -> tiers.equip_value -> tiers/__init__`; `ai/goals/` is a
sibling package with no back-edge, confirmed by `gathering.py` already
importing `reserve_floor` directly for the craft-vs-buy gate, and by a direct
import smoke test). No new SelectionContext threading needed.

WITHDRAWGOLD DEFICIT AND THE RESERVE (derivation): `gold_deficit` sizes a
WithdrawGold ferry (bank -> pocket) so NpcBuy's pocket-only gold gate can be
met. WithdrawGold is gold-CONSERVING — it moves gold between pocket and bank
but changes neither `gold_on_hand` nor the reserve invariant. The invariant
therefore binds entirely at the AFFORDABILITY check above (this leaf's spend
must leave gold_on_hand - price*qty >= reserve); once a leaf passes that gate,
sizing the withdrawal to cover the pocket shortfall (`gold_demand -
state.gold`, capped at `bank_gold`) cannot itself push the total below the
reserve, because the total is unaffected by the transfer. `gold_demand` is
now (Task 4) the sum over only the ADMITTED gold leaves (below) — the ferry
never sizes for a leaf the joint check rejected.

JOINT GOLD AFFORDABILITY (follow-up wave Task 4, 2026-07-08): Task 3's gold
gate checked each leaf against `gold_on_hand >= price*qty +
reserve_floor(state, gd, leaf)` INDEPENDENTLY. `reserve_floor(..., leaf)`
dedups only THAT leaf's own reservation, so when a closure has two (or more)
still-unowned gold-priced leaves, each leaf's independent check credits
`gold_on_hand` as if it alone were being bought — the OTHER leaf's price is
double-counted as spendable room by both checks. Concretely: leaf A costs 40,
leaf B costs 40, reserve (unrelated to either) is 30, gold_on_hand is 70. Per
leaf: A passes (70 >= 40+30=70 exactly), B passes (70 >= 40+30=70 exactly) —
but buying BOTH costs 80 > 70. Two individually reserve-safe leaves jointly
overspend the reserve by 40.

FIX — the affordability verdict for the SET of unowned gold leaves now holds
on the SUM: `Σ(price_i * qty_i for i in admitted) + reserve_floor_multi(state,
gd, admitted) <= gold_on_hand`, where `reserve_floor_multi` (progression_
reserve.py) dedups EVERY admitted leaf's own reservation from the total, not
just one — the direct multi-leaf generalization of `reserve_floor`.

ADMISSION POLICY (which leaves get admitted when the joint sum does not fit):
deterministic CHEAPEST-FIRST PREFIX. Gold-priced candidates (still-unowned,
not already affordable via an item-currency vendor) are sorted ascending by
their OWN total cost (`price * qty`) — the only semantic key, ties broken by
Python's stable sort preserving the closure walk's own deterministic
iteration order (never a repr/alphabetical tiebreak — the same "genuine ties
fall to iteration order" rule the `funding_target` scorer below already
uses, chosen over a manufactured secondary key like item level specifically
for that consistency). Walking cheapest-first, a leaf is ADMITTED when the
running spend + this leaf's cost + the reserve floor (dedupping every leaf
admitted so far, INCLUDING this one) still fits `gold_on_hand`; the FIRST
leaf that does not fit, and every leaf after it in the sorted order (each
costing >= as much), are rejected — "admission until the budget exhausts", a
simple deterministic prefix rule, not a full knapsack search (a rejected
cheap leaf is never revisited after a later, pricier leaf's larger dedup
might have freed room for it — the simpler rule is preferred so the policy
stays a one-line-provable prefix invariant rather than a combinatorial
search).

Rejected gold candidates fall through to the SAME `blocked` signal as a
leaf with no usable vendor at all (via `currency_afford_plannable_pure`,
unchanged) — is_plannable prunes exactly as before, just now on the JOINT
verdict instead of a per-leaf one that could pass two leaves that cannot
both be bought.

Item-currency legs are untouched by this task: item-currency affordability
stays per-leaf (independent stacks, no shared pool the way gold is), computed
exactly as before and never entered into the joint gold budget.

ONE closure walk serves two consumers (DRY), each reading a DIFFERENT signal:
  - `blocked`  — GatherMaterialsGoal.is_plannable fast-fails when any currency-buy
    leaf is unaffordable (currency_afford_plannable_pure is the proved live
    decision). A leaf with no usable vendor at all is also blocking.
  - `funding_target` — the arbiter routes ReachCurrencyGoal to FUND the currency.
    This fires ONLY for a leaf whose currency is `tasks_coin` (the currency
    ReachCurrencyGoal can actually produce by completing tasks — C2
    CompleteTaskAction mints tasks_coin, nothing else). A leaf priced in gold or
    a non-task currency is `blocked` when unaffordable, but is NOT a funding
    target — ReachCurrencyGoal cannot earn that currency, so routing to it would
    chase an unfundable goal; the bot earns gold/other currencies by its normal
    means instead. Among the leaf's eligible vendors, the one with the FEWEST
    funding cycles (proved `funding_cycles_pure`) is chosen — a semantic key, not
    raw price, so a cheap vendor in a currency the character barely holds does not
    out-rank a slightly pricier vendor in a currency already mostly funded.
"""
from typing import NamedTuple

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.currency_afford_core import currency_afford_plannable_pure
from artifactsmmo_cli.ai.goals.funding_core import funding_cycles_pure
from artifactsmmo_cli.ai.progression_reserve import reserve_floor_multi
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.tiers.objective import GOLD
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


class _CurrencyLeaf(NamedTuple):
    """One still-open currency-buy leaf from the closure walk, pre-classified
    by its PERMANENT (non-event, located) vendor routes. `item_affordable` is
    independent per leaf (item-currency stacks are not jointly budgeted —
    only the gold arm is, Task 4). `gold_price` is this leaf's cheapest
    permanent GOLD-vendor UNIT price, or None when no gold vendor sells it.
    `fundable` holds this leaf's tasks_coin vendor options (unchanged funding-
    target arm)."""

    leaf: str
    qty: int
    owned: int
    item_affordable: bool
    gold_price: int | None
    fundable: list[tuple[str, int, str]]


class CurrencyLeafAnalysis(NamedTuple):
    """Result of walking a recipe closure for currency-buy leaves.

    `blocked`: at least one currency-buy leaf is unaffordable (and unowned) via
    every usable vendor — GatherMaterialsGoal.is_plannable must prune.
    `funding_target`: (tasks_coin, required_amount) for the FIRST unaffordable
    leaf the arbiter can fund via ReachCurrencyGoal, or None when no unaffordable
    leaf is tasks_coin-funded.
    `gold_deficit`: how much POCKET gold is missing to cover the closure's
    still-unowned gold-buy leaves at their cheapest permanent vendors
    (max(0, gold_demand - state.gold)). NpcBuyAction's gold gate is
    pocket-only, so when affordability was granted on pocket+bank the plan
    must chain WithdrawGold → NpcBuy — GatherMaterialsGoal.relevant_actions
    sizes that withdraw edge from this figure (admit/emit symmetry). 0 when
    pocket gold alone covers (or nothing gold-priced remains to buy).
    """

    blocked: bool
    funding_target: tuple[str, int] | None
    gold_deficit: int


def _classify_leaves(
    chain: dict[str, int], state: WorldState, game_data: GameData,
) -> list[_CurrencyLeaf]:
    """Pass 1: walk the closure, keeping only currency-buy leaves (skipping
    craftable / gatherable / monster-dropped / no-vendor items), and record
    each one's item-currency affordability and cheapest gold unit price —
    the two per-leaf facts the joint gold check and the funding-target arm
    both need. Chain-walk order is preserved (deterministic, non-alphabetical:
    the same order the funding-target loop iterates below)."""
    bank = state.bank_items or {}
    leaves: list[_CurrencyLeaf] = []
    for leaf, qty in chain.items():
        # The requested item ITSELF is analyzed too: stepwise decomposition
        # hands the mapper the currency item directly once every other input
        # is in hand (satchel -> ... -> ObtainItem(jasper_crystal)), and the
        # old `leaf in needed` exclusion silenced funding exactly at that
        # final step (live satchel stall 2026-07-06). Craftable / gatherable /
        # monster-dropped requests still skip via the guards below.
        if game_data.crafting_recipe(leaf) is not None:
            continue
        if leaf in game_data.resource_drops.values():
            continue
        if game_data.monsters_dropping(leaf):
            continue
        purchases = game_data.npc_purchases(leaf)
        if not purchases:
            continue
        # PERMANENT, located vendors only — matching relevant_actions' guard, so
        # the affordability view and the emitted action set use the same vendors.
        permanent = [
            (npc, price, currency)
            for npc, price, currency in purchases
            if not game_data.is_event_npc(npc) and game_data.npc_location(npc) is not None
        ]
        owned = state.inventory.get(leaf, 0) + bank.get(leaf, 0)
        # Item-currency affordability is independent per leaf (unchanged from
        # Task 3): a separate, unshared stack per currency, never budgeted
        # jointly the way gold is below.
        item_affordable = any(
            state.inventory.get(currency, 0) + bank.get(currency, 0) >= price * qty
            for _npc, price, currency in permanent if currency != GOLD
        )
        gold_prices = [price for _npc, price, currency in permanent if currency == GOLD]
        gold_price = min(gold_prices) if gold_prices else None
        fundable = [
            (npc, price, currency)
            for npc, price, currency in permanent
            if currency == TASKS_COIN_CODE
        ]
        leaves.append(_CurrencyLeaf(leaf, qty, owned, item_affordable, gold_price, fundable))
    return leaves


def _admit_gold_leaves(
    leaves: list[_CurrencyLeaf], gold_on_hand: int,
    state: WorldState, game_data: GameData,
) -> set[str]:
    """Task 4's joint gold-affordability admission: deterministic cheapest-
    first prefix over the still-unowned, gold-only-route leaves (candidates
    already affordable via item currency never enter the gold budget at
    all). See the module docstring's ADMISSION POLICY section for the full
    derivation; this is the mechanical walk of that policy."""
    candidates: list[tuple[int, _CurrencyLeaf]] = []
    for lf in leaves:
        if lf.owned >= lf.qty or lf.item_affordable:
            continue
        price = lf.gold_price
        if price is None:
            continue
        candidates.append((price * lf.qty, lf))
    candidates.sort(key=lambda pair: pair[0])

    admitted: set[str] = set()
    gold_spent = 0
    for cost, lf in candidates:
        trial = admitted | {lf.leaf}
        reserve = reserve_floor_multi(state, game_data, frozenset(trial))
        if gold_on_hand < gold_spent + cost + reserve:
            break  # budget exhausted: this and every costlier remaining candidate rejected
        admitted = trial
        gold_spent += cost
    return admitted


def analyze_currency_leaves(
    needed: dict[str, int], state: WorldState, game_data: GameData
) -> CurrencyLeafAnalysis:
    """Walk the recipe closure of `needed` once, returning the `blocked` signal
    (for is_plannable) and the `funding_target` (for the arbiter)."""
    bank = state.bank_items or {}
    # Gold on hand: pocket + KNOWN bank gold. `bank_gold or 0` is the GAP-1
    # unknown-bank rule — None means unknown, which credits nothing (never a
    # default; the WithdrawGold edge is likewise inapplicable on a None bank).
    gold_on_hand = state.gold + (state.bank_gold or 0)
    chain: dict[str, int] = {}
    for code, qty in needed.items():
        closure_demand(code, qty, game_data, chain, frozenset())

    leaves = _classify_leaves(chain, state, game_data)
    # JOINT gold check (Task 4): the admitted set's total spend, feeding
    # gold_deficit exactly (admit/emit symmetry — the ferry never sizes for a
    # leaf the joint check rejected).
    admitted = _admit_gold_leaves(leaves, gold_on_hand, state, game_data)
    gold_demand = sum(
        (lf.gold_price or 0) * lf.qty for lf in leaves if lf.leaf in admitted)

    blocked = False
    funding_target: tuple[str, int] | None = None

    for lf in leaves:
        # affordable = via item currency (unchanged, per-leaf) OR admitted
        # into the joint gold budget. currency_afford_plannable_pure is the
        # proved live decision: a leaf is only blocking when not affordable
        # AND not already owned in sufficient quantity.
        affordable = lf.item_affordable or (lf.gold_price is not None and lf.leaf in admitted)
        if currency_afford_plannable_pure(True, affordable, lf.owned, lf.qty):
            continue

        blocked = True  # is_plannable must prune; the leaf cannot be acquired now.

        if not lf.fundable:
            continue  # gold/event/non-task currency leaf: blocked but unfundable;
            #           keep scanning for a later tasks_coin-funded blocking leaf.

        floor = game_data.min_task_coin_reward()  # ≥1, enforced at load (C2)
        # Pick the vendor needing the FEWEST funding cycles (semantic, proved
        # core), tiebreak by cheaper target then by most currency already held.
        # `min(key=s[0])` compares ONLY the semantic key; genuine ties fall to
        # iteration (vendor-data) order — never a repr/alphabetical sort.
        scored = []
        for _npc, price, currency in lf.fundable:
            target = price * lf.qty
            on_hand = state.inventory.get(currency, 0) + bank.get(currency, 0)
            key = (funding_cycles_pure(on_hand, target, floor), target, -on_hand)
            scored.append((key, currency, target))
        _key, best_currency, best_target = min(scored, key=lambda s: s[0])
        funding_target = (best_currency, best_target)
        break  # blocked is already True and we have the FIRST fundable target.

    return CurrencyLeafAnalysis(
        blocked=blocked, funding_target=funding_target,
        gold_deficit=max(0, gold_demand - state.gold))
