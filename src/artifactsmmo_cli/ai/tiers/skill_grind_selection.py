"""Pure core for skill-grind target selection: pick the in-skill item to craft
NOW to gain XP toward a skill gate, considering ONLY items that are same-skill,
in-level, obtainable (every recipe input reachable), AND xp-positive (the craft
is not in the server's zero-xp band).

`skill_grind_selection_pure` is the proved decision core (see
formal/Formal/SkillGrindSelection.lean). The impure wrapper `skill_grind_target`
hoists the `GrindCandidate`s — including the recursive `obtainable` flag and the
`xp_positive` band verdict — from GameData + holdings and delegates here.

Why obtainable matters (live weaponcrafting bug, 2026-06-13): the bot, committed
to weaponcrafting, picked `wooden_staff` (recipe needs `wooden_stick`, which has
no recipe and is not gatherable). The GatherMaterials goal then GOAP-failed
(plan_len 0) and the arbiter fell CROSS-SKILL to a gearcrafting grind. Filtering
to obtainable candidates makes selection pick the reachable `copper_dagger`
(copper_bar <- copper_ore) instead, so the committed skill actually grinds.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GrindCandidate:
    """A craftable item considered for a skill grind. `acquire_steps`,
    `obtainable`, `wanted` and `xp_positive` are HOISTED (computed against
    holdings / recipe-closure reachability / the objective's gear+tool targets /
    the server's level_penalty band by the impure wrapper) so this core stays
    pure/extractable. `wanted` = the crafted item is a current objective
    gear/tool target (`is_target`); a wanted item produces a keeper while
    leveling, a non-wanted one only a throwaway. `xp_positive` =
    `ai/skill_xp_positive` says crafting it still pays skill xp at the current
    level.

    `acquire_steps` = the WHOLE-CHAIN action cost of making one of this item
    from what the character already holds (`min_gathers + min_crafts` over the
    recipe closure, the proved lower bound from `ai/min_plan_length`). It
    replaced a one-level `mats_missing` count on 2026-08-06 — see `_beats`. As
    of 2026-08-14 it is the DENOMINATOR of a rate rather than the first
    ranking key, and a wanted rung credits it to zero — see `_beats`."""
    code: str
    craft_skill: str
    craft_level: int
    acquire_steps: int
    obtainable: bool
    wanted: bool
    xp_positive: bool


def _beats(c: GrindCandidate, best: GrindCandidate | None) -> bool:
    """True when feasible `c` strictly precedes `best` in the selection order

        (craft_level / effective_steps  desc,   # XP-proxy per action
         wanted                         desc,   # keeper breaks a rate tie
         craft_level                    desc,
         acquire_steps                  asc)    # real cost breaks the rest

    where `effective_steps` is 0 for a wanted rung and `acquire_steps`
    otherwise. A None `best` (no incumbent) is always beaten. A full tie keeps
    the incumbent (first-seen in candidate order) — deterministic without a
    string tie-break.

    RATE, NOT COST (2026-08-14). The first key was `acquire_steps` ascending —
    cheapest chain wins — and cheapness is anti-correlated with the thing a
    grind exists to produce: the cheapest in-level rung is the LOWEST-level
    one, which pays the least xp per craft. So the ranking optimised against
    its own purpose. Live Lor and HAL, both at the same moment: Lor picked
    `apprentice_gloves` (craft level 1, 13 actions) over `sticky_dagger` (5,
    59), HAL picked the same gloves (43 actions) over `water_bow` (5, 59), and
    Lor's weaponcrafting sat at 8 across 757 grind cycles. Under rate the
    order inverts — 5/59 = 0.085 beats 1/13 = 0.077 — while the 2026-08-06
    R2D2 case is UNCHANGED, because there the cheaper rung was also the faster
    one (1/7 = 0.143 against 5/51 = 0.098).

    CROSS-MULTIPLIED, NOT DIVIDED. `c.craft_level * best_steps` against
    `best.craft_level * c_steps` is the same comparison in integers. This core
    is mechanically extracted to Lean over `Int` (`scripts/extract_lean.py`),
    so a float would not survive the trip, and the cross product also disposes
    of the zero-denominator case without a special branch: a rung at zero
    effective steps makes the opposing product zero and wins on any positive
    level, with two such rungs falling through to the tie-breaks.

    `craft_level` IS A PROXY FOR XP, NOT XP. The server pays
    `Round((XP_base + (content_level / skill_level) * k) * level_penalty *
    wisdom_bonus)` and neither `XP_base` nor `k` is published or in the API
    (`ai/skill_xp_positive`). At a fixed skill level xp is monotone
    nondecreasing in content level, which justifies `craft_level` as an
    ORDINAL proxy; using it as the CARDINAL numerator of a ratio additionally
    assumes xp is proportional to it, and `level_penalty` varies across rungs
    by a factor nobody has measured. The assumption is named here rather than
    hidden: see `formal/diff/craft_xp_replay.py` for what the play-traces say
    about it.

    The `wanted` tie-break is spelled as two `and`/`not` branches rather than
    `if c.wanted != best.wanted: return c.wanted`: the extractor's v1 subset
    rejects `!=` on `Bool`, and this is the shape this function already
    extracted for two years. Semantically identical.

    WANTED IS A MARGINAL-COST CREDIT, NOT A PIVOT. A rung the objective
    already wants is work the character owes regardless of the grind, so the
    grind's marginal cost for it is zero — hence `effective_steps = 0` rather
    than a key above the rate. Crafting a wanted item gains the SAME skill xp
    and yields a keeper instead of a throwaway (2026-06-24: pure cheapest-chain
    greed made the bot craft a value-10 `apprentice_gloves` while ignoring the
    committed value-83 `copper_dagger`). Expressing that as a credit rather
    than a lexicographic pivot is what stops a wanted rung at 500 steps
    outranking a throwaway at 2 by fiat while still letting it win on merit —
    and it keeps every term in one currency, which is the argument
    `ai/skill_grind_cost_core` already makes.

    WHY THERE ARE STILL TWO TIE-BREAKS UNDER THE CREDIT. Crediting to zero
    makes every wanted rung tie every other wanted rung on rate, which destroys
    the cost signal among them — two rungs both owed are not equally near, so
    RAW `acquire_steps` is the last key. And a free throwaway also credits to
    zero, ties a wanted keeper at rate zero, and would survive on insertion
    order — the 2026-06-24 inversion through the back door — so `wanted` is the
    first tie-break under the rate. Neither is decoration; each closes a case
    the credit alone gets wrong.

    HISTORY. This is the fourth attempt at this ordering. `wanted`
    (2026-06-24), the `xp_positive` FILTER (2026-08-05, live Robby, 288
    zero-xp cycles), and `acquire_steps` replacing a one-level `mats_missing`
    count (2026-08-06, live R2D2, 129 cycles) were each real, and each was
    another key bolted onto a first key that was lying about what a grind is
    for. This one replaces that first key.
    """
    if best is None:
        return True
    c_steps = 0 if c.wanted else c.acquire_steps
    best_steps = 0 if best.wanted else best.acquire_steps
    c_rate = c.craft_level * best_steps
    best_rate = best.craft_level * c_steps
    if c_rate != best_rate:
        return c_rate > best_rate
    if c.wanted and not best.wanted:
        return True
    if best.wanted and not c.wanted:
        return False
    if c.craft_level != best.craft_level:
        return c.craft_level > best.craft_level
    if c.acquire_steps != best.acquire_steps:
        return c.acquire_steps < best.acquire_steps
    return False


def skill_grind_selection_pure(
    skill: str, current_level: int, candidates: list[GrindCandidate],
) -> str:
    """The in-skill item to craft for `skill` XP at `current_level`, or "" when
    none qualifies (caller falls back to LevelSkill on the SAME skill).

    Considers ONLY candidates that are same-skill (`craft_skill == skill`),
    in-level (`craft_level <= current_level`), `obtainable`, and `xp_positive`.
    Among those, returns the `_beats`-maximal candidate's code. Returns "" iff
    none qualify.

    XP-POSITIVE is a FILTER, not a tie-break (live Robby 2026-08-05, 14h at
    character level 22 with 288 zero-xp `LevelSkill(woodcutting->20)` cycles):
    at woodcutting 15 the in-level rungs were `ash_plank` (craft level 1) and
    `spruce_plank` (10), and because `mats_missing` is the ranking's FIRST key
    the grind picked whichever rung's materials were already stockpiled — the
    grey `ash_plank`, whose craft pays nothing 14 levels down. The bot then
    crafted it forever with `woodcutting` xp pinned at 4229 across 104
    consecutive `ok` cycles. Ordering cannot fix this: a rung that pays ZERO is
    worthless at ANY `mats_missing`, so it must be excluded from the candidate
    set rather than merely ranked below. Cheap materials CORRELATE with obsolete
    tiers, which is what made the greedy key pick the one useless rung."""
    best: GrindCandidate | None = None
    for c in candidates:
        if (c.craft_skill != skill or c.craft_level > current_level
                or not c.obtainable or not c.xp_positive):
            continue
        if _beats(c, best):
            best = c
    return best.code if best is not None else ""
