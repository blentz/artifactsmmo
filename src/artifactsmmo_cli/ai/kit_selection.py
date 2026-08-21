"""Which weapon/tools the character is actually WORKING with: the best fighting
weapon and the best gathering tool per skill, over inventory + equipped — and
the best one OWNED, which additionally ranges over the BANK.

Extracted from `ai/bank_selection.py` (where the deposit keep-set used to live)
so the keep authority can ask the same question without an import cycle:
`bank_selection` now asks `inventory_keep.bankable` how many copies it may bank,
and `inventory_keep`'s COMBAT_WEAPON / WORKING_KIT reasons ask THESE selectors
which single copy is the working one. Both modules import this one; it imports
neither.

TWO SCOPES, because the keep authority asks two different questions:

  * `best_fighting_weapon` / `best_gathering_tools` (bag + equipped) — "what am
    I WORKING with?". This is the BAG cap's question: the copy that must not be
    deposited, or the gather re-arm goes bare-handed (trace 2026-07-05).
  * `best_owned_fighting_weapon` / `best_owned_gathering_tools` (bag + bank +
    equipped) — "what is the best one I OWN?". This is the OWNERSHIP cap's
    question: never DESTROY your last tool/weapon. A tool held entirely in the
    BANK (the state `DepositAll` produces once the one bag copy is spent or
    equipped) is invisible to the bag-scoped selector, so an ownership cap fed
    from it would license melting every copy the character has.

The owned scope is a SUPERSET of the bag scope's candidates, but its winner may
differ (a better tool sitting in the bank), so the keep authority takes the
UNION of the two answers: the working copy keeps its bag slot AND the best owned
copy survives destruction. The owned arm never shrinks the bag protection.

These selectors identify a CODE, never a quantity. The quantity is the keep
authority's business — and it is 1, because a character swings one weapon and
mines with one pickaxe. Conflating "this code is the working tool" with "keep
every copy of this code" is exactly the hoard bug this epic exists to kill
(18 `copper_axe` in the bag, all shielded, none banked).
"""

import weakref
from collections import OrderedDict

from artifactsmmo_cli.ai.equipment.scoring import gather_score
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import _GATHERING_SKILLS
from artifactsmmo_cli.ai.world_state import WorldState


def _banked(state: WorldState) -> set[str]:
    """Codes the character owns in the BANK (held copies only)."""
    return {code for code, qty in (state.bank_items or {}).items() if qty > 0}


def _pick_weapon(candidates: set[str], game_data: GameData) -> str | None:
    """Highest-attack non-tool weapon among `candidates`, or None.

    Tools (pickaxe/axe/net) have skill_effects and are excluded — they are
    gathering aids, not the combat weapon to protect.

    Memoized on the same key and for the same reason as `_pick_tools`: it is the
    other half of the keep authority's per-node question. With `_pick_tools`
    memoized this became the top cost of the same search — 229,300 calls, 4.5 of
    15 seconds — which is what fixing one half of a pair looks like.
    """
    _, cache = _cache_for(game_data)
    key = frozenset(candidates)
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    best: tuple[int, str] | None = None
    for code in candidates:
        stats = game_data.item_stats(code)
        if stats is None or stats.type_ != "weapon" or stats.skill_effects:
            continue
        attack = sum(stats.attack.values()) if stats.attack else 0
        # Higher attack wins; tie broken by code ascending (deterministic).
        if best is None or attack > best[0] or (attack == best[0] and code < best[1]):
            best = (attack, code)
    answer = best[1] if best else None
    cache[key] = answer
    if len(cache) > _KIT_MEMO_MAX:
        cache.popitem(last=False)
    return answer


#: Per-`GameData` memos for `_pick_tools` / `_pick_weapon`, keyed on the
#: candidate SET.
#:
#: `inventory_keep.reason_quantity` asks the keep authority on every planner node
#: expansion, and the keep authority asks these selectors which copy is the
#: working one. Unmemoized they rescanned `candidates` x every gathering skill
#: per node, with a bag that barely changes between siblings. Measured on live
#: C3P0 (2026-08-21), one `UpgradeEquipment(iron_ring->ring2_slot)` search:
#: 63,732 calls into `_pick_tools`, 10,856,432 `gather_score` calls, 11.0s of a
#: 15.02s budget — 73% of a plan that then TIMED OUT and was memoised doomed.
#: 16.6 ms/node -> 1.9 ms/node with both memoized (`_pick_weapon` became the top
#: cost the moment `_pick_tools` stopped being it — fixing one half of a pair
#: only moves the cost).
#:
#: KEYED PER `GameData`, following `equipment/loadout_cache`. The catalog is a
#: determinant of the answer, and a process-global key is unsound the moment two
#: catalogs exist: the test suite builds a fresh `GameData` per test, and a
#: candidates-only key served one test's answer to another's items (six
#: `formal/diff/test_bank_selection_diff` failures that passed in isolation).
#: `weakref.finalize` drops the entry with the catalog, which is also what makes
#: `id()` safe against reuse.
_tool_caches: "dict[int, OrderedDict[frozenset[str], frozenset[str]]]" = {}
_weapon_caches: "dict[int, OrderedDict[frozenset[str], str | None]]" = {}
_KIT_MEMO_MAX = 4096


def _cache_for(game_data: GameData) -> tuple[
        "OrderedDict[frozenset[str], frozenset[str]]",
        "OrderedDict[frozenset[str], str | None]"]:
    key = id(game_data)
    tools = _tool_caches.get(key)
    if tools is None:
        tools = OrderedDict()
        weapons: OrderedDict[frozenset[str], str | None] = OrderedDict()
        _tool_caches[key] = tools
        _weapon_caches[key] = weapons
        weakref.finalize(game_data, _tool_caches.pop, key, None)
        weakref.finalize(game_data, _weapon_caches.pop, key, None)
    return tools, _weapon_caches[key]


def _pick_tools(candidates: set[str], game_data: GameData) -> frozenset[str]:
    """Best tool per gathering skill (by ``tool_value``) among `candidates`.

    Tool magnitude is ``abs(gather_score)`` (== tiers.equip_value.tool_value,
    which cannot be imported here: tiers.__init__ -> strategy -> guards ->
    bank_selection cycles).

    Returns a FROZENset: the answer is memoized and both callers hand it
    straight back, so a mutable one would let a single caller's `.add()`
    corrupt every later node.
    """
    cache, _ = _cache_for(game_data)
    key = frozenset(candidates)
    hit = cache.get(key)
    if hit is not None:
        cache.move_to_end(key)
        return hit
    tools: set[str] = set()
    for skill in _GATHERING_SKILLS:
        best: tuple[int, str] | None = None
        for code in candidates:
            stats = game_data.item_stats(code)
            value = abs(gather_score(stats, skill)) if stats is not None else 0
            # Bigger reduction wins; tie broken by code ascending (deterministic).
            if value > 0 and (best is None or value > best[0]
                              or (value == best[0] and code < best[1])):
                best = (value, code)
        if best is not None:
            tools.add(best[1])
    answer = frozenset(tools)
    cache[key] = answer
    if len(cache) > _KIT_MEMO_MAX:
        cache.popitem(last=False)
    return answer


def _held_weapon_candidates(state: WorldState) -> set[str]:
    """Weapon codes to hand: every bag STACK plus what is equipped. The stack is
    counted regardless of quantity — this is the candidate set
    `Formal.BankSelection`'s proved `criticalCodes` mirror ranges over
    (`formal/diff/test_bank_selection_diff.py`), and narrowing it here would
    diverge the production selector from the proof."""
    candidates: set[str] = set(state.inventory)
    candidates.update(code for code in state.equipment.values() if code)
    return candidates


def _held_tool_candidates(state: WorldState) -> set[str]:
    """Tool codes to hand: bag stacks the character actually HAS (qty > 0) plus
    what is equipped."""
    candidates: set[str] = {code for code, qty in state.inventory.items() if qty > 0}
    candidates.update(code for code in state.equipment.values() if code)
    return candidates


def best_fighting_weapon(state: WorldState, game_data: GameData) -> str | None:
    """The weapon the character is WORKING with — best over bag + equipped."""
    return _pick_weapon(_held_weapon_candidates(state), game_data)


def best_owned_fighting_weapon(state: WorldState, game_data: GameData) -> str | None:
    """The best fighting weapon the character OWNS — bag + bank + equipped. The
    ownership cap's question: destroying this one leaves the character unarmed
    even though the copies sat safely in the bank."""
    return _pick_weapon(_held_weapon_candidates(state) | _banked(state), game_data)


def best_gathering_tools(state: WorldState, game_data: GameData) -> frozenset[str]:
    """Best tool per gathering skill among what is to hand (bag + equipped) —
    the working kit. Depositing it undoes the WithdrawTools ferry and re-creates
    the bare-handed grind (trace 2026-07-05: copper_pickaxe banked, 261/300
    cycles mining with copper_dagger). Outclassed spares stay bankable — and so
    does every SPARE COPY of the kept tool itself, which is the keep authority's
    job (WORKING_KIT keeps 1), not this selector's."""
    return _pick_tools(_held_tool_candidates(state), game_data)


def best_owned_gathering_tools(state: WorldState, game_data: GameData) -> frozenset[str]:
    """Best tool per gathering skill among everything OWNED — bag + bank +
    equipped. The ownership cap's question: a tool held only in the BANK is
    still the character's last tool, and melting it leaves them bare-handed with
    nothing to ferry back."""
    return _pick_tools(_held_tool_candidates(state) | _banked(state), game_data)
