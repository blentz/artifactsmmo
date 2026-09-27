"""THE oracle for "can this character obtain item X by killing something?".

ONE answer, consulted by both sides of the plan pipeline:

  * SELECTION  — the reachability walks that decide WHAT to pursue. The
    obtain model (`tiers/skill_grind_target.is_obtainable`,
    `tiers/objective.is_attainable_now`) reads the same drop gates through
    `obtain_model/drop_routes.py`; `tiers/strategy._producible` calls this
    oracle. These are pure game-data walks: they run before any action list
    exists and must not depend on one.
  * EMISSION   — `ai/drop_fight_selection.select_drop_fight`, which turns the
    verdict into the single `FightAction` a goal plans with.

WHY IT EXISTS (live Robby, 2026-08-03, L21 jewelrycrafting 14). The two sides
answered differently and the grind sat in the gap: rung selection called
`iron_ring` buildable because its `wool` input had a winnable, spawn-known
dropper, while emission refused the only edge that could build it because that
dropper (`sheep`, L5) is GREY and `grey_farm_allowed("wool", ...)` said no. The
planner found no plan, `_execute_level_skill` raised "grind produced no leg", and
the arbiter re-picked the same rung forever — 8 of 16 consecutive live cycles,
and every one of the 54 "produced no leg" records across 39 older traces.
`890966e1` fixed the symptom by threading the grind's grey exemption into
emission's caller; this module removes the freedom to diverge again.

Before the unification the two sides disagreed on FOUR axes:

  1. liveness   — selection asked `monster_spawn_known`, emission asked "is there
                  a FightAction for this monster in the list I was handed".
  2. grey       — emission consulted the grey policy, selection did not.
  3. choice     — selection was an `any(...)`, emission ran the proved
                  expected-kills argmin and then VETOED the whole item when the
                  argmin happened to be grey (so a grey nearest-dropper could
                  mask a perfectly fightable xp-positive one).
  4. policy source — `allow_grey` came from a different expression at each site.

All four now resolve here. Liveness is `monster_spawn_known` on both sides.

ONE SET OF DROP GATES (Phase 1 step 4 of docs/PLAN_decision_architecture_redesign.md).
The gates themselves are evaluated in `ai/obtain_model/drop_routes.py`, which the
unified obtain model uses too; this oracle is the `Policy` that enforces the
routable spawn (`spawn_known`) and the caller's grey rule (`allow_grey`),
where the obtain model's LEGACY policy asks for a live tile and has no grey rule
(the D-D difference, now one explicit switch instead of two implementations). The
grey rule is a FILTER on the candidate set, not a post-choice veto, so the
proved choice core (`select_monster_for_drop`) only ever ranks droppers this
oracle has already approved — the choice can no longer change the verdict.

CONTRACT
--------
`fightable_droppers(item, state, game_data, allow_grey=P)` returns exactly the
monsters the planner is permitted to kill for `item` from `state` under grey
policy `P`. It PROMISES:

  * every returned dropper is winnable now, spawns somewhere the movement model
    can route to, and is either xp-positive or explicitly grey-permitted;
  * `select_drop_fight` with the SAME `item`, `state` and `allow_grey` refuses
    only when it can find no `FightAction` for ANY returned dropper — it applies
    no gate of its own beyond that lookup;
  * consequently `drop_obtainable(...) is False` ⇒ `select_drop_fight(...) is
    None`. A selection walk that calls this can never promise a route emission
    will not build.

NAMED RESIDUAL (the one thing this oracle cannot see)
-----------------------------------------------------
The oracle has no `actions` list, so it cannot know whether the caller's action
pool actually contains a `FightAction` for an approved dropper. `select_drop_fight`
may therefore still return None while `drop_obtainable` is True, in exactly one
case: **no FightAction exists in the passed pool for any approved dropper.**

That residual is empty for the production pool by construction, not by luck:
`actions/factory.build_actions` emits a `FightAction` for every key of
`all_monster_locations` (static map + active-event tiles + open-raid tiles) and
for every layered non-overworld content code that is a known monster — which is
a superset of what `monster_spawn_known` accepts (it accepts a monster with a
non-empty `monster_locations`, i.e. an `all_monster_locations` key, or one whose
layered tiles sit in a REACHABLE region, i.e. a subset of the layered codes the
factory emits). It is non-empty only for a caller that hands `select_drop_fight`
a hand-filtered or synthetic action pool. Such a caller is asking a narrower
question than this oracle answers, and must treat the None as "not with THIS
pool", never as "not obtainable".

GREY POLICY is NOT decided here. `allow_grey` stays the caller's, because the
callers legitimately differ and folding any default in would silently change the
others — see `ai/grey_farm.py` for the 2026-07-06 user directive and the three
structural exemptions from it.

`is_winnable` is called COLD (no `LearningStore`), the convention every planning
path uses — see `ai/combat_targets`. The one site that wants the learned-loss
veto is `player.PlanReport`'s diagnostic drop listing, which says so at its call
site and is deliberately not routed through here.

SITES THAT ASK A NEARBY BUT DIFFERENT QUESTION, and why they stay separate:
  * `tiers/objective._drops_from_spawning_monster` — state-INDEPENDENT (no
    `is_winnable` at all): the perfect-sheet target assumes full progression, so
    any spawning monster's drops count. A different question, not a weaker one.
  * `audit/craft_completeness._leaf_gap` — must report WHICH limit blocks a leaf
    (COMBAT_BLOCKED / GREY_FARM_SUPPRESSED / EVENT_GATED), not a yes/no, and it
    excludes event monsters because the census is an event-free audit.
  * `craft_plan_gen`'s drop arm — a LOOKUP over an action list this oracle has
    already narrowed to one dropper fight, not a verdict of its own.
  * `obtain_sources`, `requirement_graph`, `bid_vs_craft`, `objective_needs`,
    `strategy_driver.monster_drop_inputs` — "does this item have a dropper at
    all", a source-KIND classification with no character in it.
"""

from dataclasses import replace

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_routes
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY
from artifactsmmo_cli.ai.world_state import WorldState


def fightable_droppers(item: str, state: WorldState, game_data: GameData,
                       *, allow_grey: bool) -> list[tuple[str, int, int, int]]:
    """Drop-table rows `(monster_code, rate, min_qty, max_qty)` for every monster
    the planner may kill for `item` from `state`.

    Three gates, in the order a plan would hit them:

    * SPAWN — `monster_spawn_known`: the monster appears on a tile the movement
      model can actually route to. A catalog monster with no routable spawn (a
      raid boss with no map tile, content behind an unmodeled transition edge)
      is not a source, however winnable it looks on paper.
    * COMBAT — `is_winnable` AT RESTORABLE HP: never offer a fight the character
    loses when healthy. Evaluated at `max_hp`, not at current hp, because this
    answers "is there a ROUTE" and Rest is an action the planner has.
    `combat.predict_win` reads CURRENT hp deliberately (see its docstring — a
    damaged character really does lose fights a healthy one wins), and that is
    the right basis for the runtime question "take this fight NOW", still asked
    at `player.py:1047`, `player.py:3742`, `combat_targets.py:88` and
    `tiers/guards.py:215`. Asking it HERE made route existence swing on combat
    noise: measured live 2026-08-17, C3P0 at 63/315 hp had no route to `wool`
    and priced `iron_shield` at 3,000,926; the same character at 315/315 priced
    it at 926 — a factor of ~7,000 in a RANKING key.

    The downstream gates are untouched, which is what makes planning through a
    rest safe: `FightAction._structurally_applicable` still refuses below
    `_MIN_FIGHT_HP_FRACTION`, and `GuardKind.RESTORE_HP` exists precisely to
    rest for a fight that is winnable rested and not winnable now. The planner
    may plan through a rest; the executor may not walk into a losing fight.
    * GREY — a zero-xp dropper is offered only when `allow_grey`. Dropping it
      from the CANDIDATE SET rather than vetoing the item after the argmin is
      deliberate: a nearby grey dropper must not mask a fightable xp-positive
      one, and it keeps this verdict independent of the choice rule.

    Empty list = no route from here. Order is the drop table's, so the caller's
    argmin sees the same candidates in the same order every cycle."""
    # Resting restores hp and NOTHING else, so `xp_per_kill` below keeps reading
    # the ORIGINAL state: the grey gate is about the character's LEVEL, which a
    # rested copy shares, and threading the copy there too would blur two gates
    # that must stay readable as separate things.
    # The gates live in `obtain_model.drop_routes`, shared with the obtain model;
    # this oracle is the policy that enforces them: a routable spawn
    # (`SPAWN_KNOWN`), winnable at restorable hp, and xp-positive unless
    # `allow_grey`. Checked equal to the previous inline body over every item of
    # all 44 scenario worlds, both grey settings, before the switch (46,024
    # comparisons, 0 differences).
    policy = replace(LEGACY, allow_grey=allow_grey)
    ready = {route.via for route in drop_routes(item, state, game_data) if policy.ready(route)}
    return [row for row in game_data.monsters_dropping(item) if row[0] in ready]


def drop_obtainable(item: str, state: WorldState, game_data: GameData,
                    *, allow_grey: bool) -> bool:
    """The boolean face of `fightable_droppers` for reachability walks that only
    ask yes/no. Same verdict, same gates — never a second implementation."""
    return bool(fightable_droppers(item, state, game_data, allow_grey=allow_grey))
