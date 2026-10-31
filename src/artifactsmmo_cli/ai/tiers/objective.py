"""The gear-target classifier and the perfect-sheet attainability walk.

`CharacterObjective.classify_target` answers whether one gear piece can be had
from the character's state now, or names the first blocker in front of it; the
gear objective's pieces (`decisions.which_piece_is_next.piece_target`) are
classified through it. `is_attainable` is the state-independent "producible at
max progression" walk, grounded by `Formal.Objective.is_attainable_eq_grounding`.

The old gear sheets (the endgame per-slot sheet, the near-term upgrade sheet,
the catalogue-best sheet, the tool sheet and the utility-potion sheet) and the
`pursuit_value` ruler they ranked on were deleted in plan C Task 6: the gear
objective `L*` (`ai/gear_objective`) is the one gear sheet."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import Policy
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.leaf_attainable_core import leaf_attainable_pure
from artifactsmmo_cli.ai.world_state import WorldState

ATTAINABILITY_ALLOWS_GREY = True
"""The grey policy the ATTAINABILITY walks pass to the shared drop oracle
(`ai/drop_obtainability`) — here and in `tiers/strategy`, which imports it from
this module so the two cannot drift.

Attainability asks "is there a real acquisition source at all", a reachability
question the 2026-07-06 grey directive does not arbitrate: that directive
chooses between farming greys for a soon-obsolete recipe and grinding the skill
for its successor, and BOTH of those are attainable routes. Suppressing greys
here would mark an item unattainable that the tree can genuinely pursue —
and the goal that pursues it (`UpgradeEquipmentGoal`, GAP-6) already carries
its own structural exemption from the directive. Named rather than a bare
`True` so the choice is visible to the next reader, and grep-able against
`skill_grind_target.GRIND_ALLOWS_GREY`, the other standing exemption."""


GOLD = "gold"
"""The currency code for ordinary (gold) purchases (`NPCItem.currency`).
Distinguished as ALWAYS attainable: the perfect sheet assumes full gold, and
gold is earnable by any fight/sell. A non-gold currency is an item code whose
own attainability must be established by recursion."""


def _attainable_closure(code: str, game_data: GameData,
                        leaf_ok: Callable[[str, frozenset[str]], bool],
                        _path: frozenset[str] = frozenset()) -> bool:
    """The perfect-sheet (`is_attainable`) producibility walk: an item is
    attainable iff it has a craft recipe whose materials are all attainable,
    else its `leaf_ok` holds. `leaf_ok` receives the current `_path` so a
    purchase edge can recurse on its currency's attainability under the same
    cycle guard. Mirrors the proved `Formal.Objective.attainAux`, parametric in
    its leaf (`drop`) and purchase (`buys`) relations. Cycle-safe via `_path`.

    The near-term gate shared this walk, with a held-stock short-circuit,
    until it moved onto the obtain model (`near_term_model`)."""
    recipe = game_data.crafting_recipe(code)
    if recipe is not None:
        if code in _path:
            return False
        sub_path = _path | {code}
        return all(_attainable_closure(mat, game_data, leaf_ok, sub_path)
                   for mat in recipe)
    return leaf_ok(code, _path)


def _gatherable(code: str, game_data: GameData) -> bool:
    """A raw resource-drop leaf: any item a gatherable resource can drop.

    GAP-2 (2026-07-07): previously consulted only the PRIMARY drop map
    (`resource_drops`, one drop code per resource — the rate-best entry),
    which understates real gatherability: rare secondary drops (gem stones
    off ordinary rocks, `small_pearls` off fishing spots) are invisible to
    it even though they are genuine, if infrequent, gathering yields.
    `gatherable_drop_items()` is the FULL drop set (grown for exactly this
    reason — see its docstring). Attainability is a reachability question
    ("is there a real acquisition source at all"), not a rate judgment —
    filter-at-use-time stays downstream (planning/cost layers weigh rate,
    this gate only asks yes/no)."""
    return code in game_data.gatherable_drop_items()


def _drops_from_spawning_monster(code: str, game_data: GameData) -> bool:
    """Some monster with a KNOWN spawn (static overworld or active event, bosses
    included) drops `code`. State-INDEPENDENT: the perfect sheet assumes full
    progression, at which any spawning monster is farmable, so its drops count
    as producible regardless of current combat strength."""
    return any(game_data.monster_spawn_known(monster_code)
               for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(code))


def _permanent_vendor_purchases(code: str, game_data: GameData) -> list[tuple[int, str]]:
    """(price, currency) for each PERMANENT, reachable NPC vendor that sells
    `code`. Event vendors (timed spawn) and unlocated NPCs are excluded: a
    perfect-sheet acquisition source must be reliably reachable, not a window
    that may be closed. Mirrors the `EventWindow` gating used for event
    merchants."""
    return [(price, currency)
            for npc, price, currency in game_data.npc_purchases(code)
            if not game_data.is_event_npc(npc) and game_data.npc_location(npc) is not None]


def is_attainable(code: str, game_data: GameData) -> bool:
    """True when the item is producible AT MAX PROGRESSION: its craft chain
    bottoms out in leaves that are gatherable raws, drops from a known-spawn
    monster (bosses included), OR PURCHASABLE from a permanent vendor for an
    attainable currency. State-independent — the perfect-sheet target ignores
    current skills, combat strength, and gold.

    Previously GATHERING-ONLY (dropped monster-drop armor — body/leg/amulet),
    then gather-or-monster-drop (task #11). The purchase edge (task #12) adds the
    rune/artifact/bag slots, whose items are NPC-only: an item with no recipe is
    attainable if a permanent vendor sells it for `gold` (always attainable) or
    for a currency item that is itself attainable (recursion, cycle-guarded via
    the closure path — e.g. a rune bought with sandwhisper_coin which is itself
    earned/dropped)."""
    def leaf_ok(leaf: str, path: frozenset[str]) -> bool:
        # Cycle guard for the recursive buyable path only — gatherable/drop/task-earnable
        # don't recurse so they're not subject to the path check.
        buyable = leaf not in path and any(
            currency == GOLD
            or _attainable_closure(currency, game_data, leaf_ok, path | {leaf})
            for _price, currency in _permanent_vendor_purchases(leaf, game_data))
        return leaf_attainable_pure(
            _gatherable(leaf, game_data),
            _drops_from_spawning_monster(leaf, game_data),
            game_data.is_task_earnable(leaf),
            buyable)

    return _attainable_closure(code, game_data, leaf_ok)


NEAR_TERM_POLICY = Policy(all_gather_routes=True, gather_skill_gate=False, craft_skill_gate=False,
                          event_vendors=False, spawn_known=True,
                          allow_grey=ATTAINABILITY_ALLOWS_GREY, vendor_routes=True,
                          price_climbs=False,
                          ge_routes=False, task_rewards=True, fight_gold=False, drop_routes=True)
"""What `classify_target` counts as obtainable now, as an obtain-model policy (step 4 of
docs/PLAN_decision_architecture_redesign.md): every resource that drops an
item (the FULL drop union: rare secondary drops, e.g. gem stones, are real
gathering yields, GAP-2), a routable spawn, grey droppers
(`ATTAINABILITY_ALLOWS_GREY`), permanent vendors paid from the pocket, and the
task board (a task-earned currency such as `tasks_coin` is producible from any
state). No GE fill, as before: goal emission fills a GE order only as the
cheaper venue for an item an NPC also sells (D-E), so a target reachable only
through the GE would be a root nothing plans. Measured live 2026-09-27: with
fills counted, every character gained 8-10 near-term targets (`bandit_armor`,
`lich_crown`, ...) that only a GE order supplied. Neither skill gate: the walk is materials-only, and `classify_target`
checks the target's own crafting skill FIRST for exactly that reason."""


def near_term_model(state: WorldState, game_data: GameData) -> ObtainModel:
    """The obtain model `classify_target` asks whether one item can be had from
    `state`: a store-less feasibility walk under `NEAR_TERM_POLICY`, every drop
    at its API prior, passed explicitly (ruling T16b). One model answers the
    target and each of its materials.

    Winnability is judged AT FULL HP (`obtain_model/drop_routes.py`): "can the
    character ever farm this" is strategic and rest is always available. A gold
    price is paid from the pocket (`state.gold`), bank gold not counted (D-H).
    Held and banked stock counts in quantity; banked copies through the model's
    WITHDRAW route, under `NO_PROFILE_CONTEXT`, whose bank is accessible (D-I).
    A craftable item is asked through its recipe and through any permanent
    vendor for it."""
    return ObtainModel(state, game_data,
                       replace(NO_PROFILE_CONTEXT, learned_drops=LearnedDrops.empty()),
                       datetime.now(UTC))


def feasible_now(model: ObtainModel, code: str) -> bool:
    """One `code` obtainable now under `NEAR_TERM_POLICY`: the question
    `classify_target` asks of its target and each material, of `model`
    (`near_term_model`)."""
    return model.feasible(code, 1, NEAR_TERM_POLICY)


@dataclass(frozen=True)
class GearTarget:
    """A per-slot target and, when it cannot be built today, WHY.

    A filter that drops unattainable candidates answers "what can I build
    today" and hides "what do I need". Live 2026-08-22: eight weapons each
    unlocked a fight Robby could not win, every one failed the near-term
    attainability walk, so the best surviving candidate was the battlestaff he
    already wore and no weapon root existed at all.

    The blocker is typed rather than a formatted string a consumer would have
    to parse back apart. `blocking_skill`/`blocking_skill_level` carry the
    skill gate (`classify_target`'s first, unconditionally-blocking check);
    `blocker` carries the code of the material still out of reach (or the
    target's own code, when it is a leaf with no recipe). Exactly one of
    `blocking_skill` and `blocker` is set when `attainable` is False; both are
    unset (`None`) when `attainable` is True.
    """

    code: str
    attainable: bool
    blocker: str | None
    blocking_skill: str | None = None
    blocking_skill_level: int = 0
    """The crafting/gathering level `code`'s recipe actually demands of
    `blocking_skill`. `decisions.root.IsThisTargetBlocked` deliberately does
    NOT read this — it asks for `current + 1` instead, so the graph
    re-derives the next rung from live state every cycle rather than
    committing to the whole climb in one shot (see that class's docstring).
    So this field's only production reader today is `formal/diff/mutate.py`'s
    "the skill-gated arm demands the whole climb instead of +1" mutant, which
    swaps `current + 1` for `self.target.blocking_skill_level` to prove the
    incremental-climb choice is load-bearing. Kept as real, correctly-typed
    data anyway (branch review F5) — it is exactly the number a future reader
    debugging "how far is the actual gate" would want next to the incremental
    step, and dropping it would re-derive the mutant on a strictly weaker
    property (`current + 1` vs `current`, an off-by-one, not "ignores the
    recipe's real requirement on purpose")."""



@dataclass(frozen=True)
class CharacterObjective:
    """The gear-target classifier over one catalogue: `classify_target` asks a
    piece of the state it is given. Built once from game data."""

    _game_data: GameData = field(repr=False, compare=False)

    @classmethod
    def from_game_data(cls, game_data: GameData) -> "CharacterObjective":
        return cls(_game_data=game_data)


    def classify_target(self, code: str, state: WorldState) -> GearTarget:
        """Attainable now, or the first blocker standing in front of it.

        The crafting-skill gate is checked BEFORE the obtain model, not
        after. The model under `NEAR_TERM_POLICY` is materials-only — it never
        inspects `crafting_skill`/`crafting_level` — so if the skill check ran
        second, it would be unreachable for any target whose materials happen
        to be reachable: the model would already have answered feasible
        and short-circuited the classification. Fix-round-1 (2026-08-23)
        found 17 live bundle items exactly in that shape — e.g. `maple_plank`
        (woodcutting@40, character at 30) reported `attainable=True,
        blocker=None` although the character cannot perform that craft at
        all. Structurally the same bug Task 5 fixed in
        `objective_step_goal` (an earlier check masking a later one, there
        the monster-drop branch masking the skill gate); the fix here is the
        same shape: reorder so the gate that is unconditionally blocking
        (no skill, no craft, regardless of material stock) is tested first.
        Do not swap 1 and 2 back — that reintroduces the mask."""
        stats = self._game_data.item_stats(code)
        if (stats is not None and stats.crafting_skill
                and state.skills.get(stats.crafting_skill, 1) < stats.crafting_level):
            return GearTarget(
                code=code, attainable=False, blocker=None,
                blocking_skill=stats.crafting_skill,
                blocking_skill_level=stats.crafting_level)
        # The target and each of its materials are asked of one state: one
        # model (`near_term_model`) answers them all.
        model = near_term_model(state, self._game_data)
        if feasible_now(model, code):
            return GearTarget(code=code, attainable=True, blocker=None)
        recipe = self._game_data.crafting_recipe(code) or {}
        for material in sorted(recipe):
            if not feasible_now(model, material):
                return GearTarget(code=code, attainable=False, blocker=material)
        return GearTarget(code=code, attainable=False, blocker=code)
