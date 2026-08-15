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
    by a factor nobody has measured. Measured over 450 craft cycles (214
    paying, 236 exact zero) across 25 distinct (craft_level, skill_level)
    pairs (formal/diff/craft_xp_replay.py), on a per-ITEM basis (xp /
    (executions * craft.quantity) -- three of the thirteen items measured
    here craft 2-at-a-time): xp / craft_level is NOT constant at fixed
    skill_level in 10 of the 11 qualifying buckets (the 11th, skill_level
    21, is trivially flat -- both craft_levels there already sit in the
    zero-xp grey band). Where both rungs pay (skill_level 5/7/8/9,
    craft_level 1 vs 5) the ratio RISES 2.36x-4.37x (craft_level 1 pays ~5-6
    xp/item, craft_level 5 pays ~59-131 depending on the item) --
    craft_level UNDERSTATES the level-5 rung's true payoff by that same
    factor, which always biases the rank toward the cheaper low rung. Where
    the comparison instead runs craft_level 1 against craft_level 10
    (skill_level 10: copper_bar -> iron_bar, a real mining refining chain;
    skill_level 11: copper_bar against spruce_plank, which is neither a
    refining chain nor one skill -- ash_plank has no skill_level-11
    observation at all) the ratio FALLS to 48% and 46% of its craft_level=1
    value. The single
    exception across the whole table: skill_level 15, craft_level 5 vs 15
    (life_amulet -> life_ring), where the ratio moves only 24.80 -> 26.87
    (+8%) -- the one comparison where craft_level's implied proportionality
    comes closest to holding, named here rather than left out of the
    picture it complicates. craft_level therefore ORDERS rungs correctly
    (monotonicity is not in question) but misprices the ratio in both
    directions depending on the pair, and the right numerator is directly
    observable per item in these traces (13 distinct items measured here).
    Not done here; recorded as a residual for a later branch.

    THAT MEASUREMENT IS PARTLY CROSS-SKILL; THIS COMPARISON NEVER IS. The
    replay groups by (skill_level, craft_level) with NO skill component, so a
    bucket can pit rungs of different skills against each other, and five of
    the eleven qualifying buckets do: skill_level 5 (ash_plank, woodcutting,
    against gearcrafting/jewelrycrafting/weaponcrafting rungs), 7 (ash_plank
    against small_health_potion, alchemy), 8 and 9 (copper_bar, mining,
    against that same potion) and 11 (copper_bar against spruce_plank,
    woodcutting). The first four are ALL FOUR buckets behind the RISES figure
    above. Since XP_base and k are per-SKILL parameters, a rise measured
    across skills can be a difference between skills rather than a craft_level
    effect. Within-skill steps exist at skill_level 10, 12, 13 and 21 (mining,
    copper_bar -> iron_bar; at 12 a cooking rung is pooled into the
    craft_level-1 mean), at 15 (life_amulet -> life_ring, jewelrycrafting) and
    at 17 (alchemy) -- and only two of those have BOTH rungs out of the grey
    band: skill_level 10 and the 5 -> 15 step at skill_level 15. The REFUTED
    verdict does not rest on the cross-skill buckets (skill_level 10 alone,
    mining against mining, moves the ratio 5.000 -> 2.400), but the DIRECTION
    and SIZE of the mispricing are far less settled than the figures above
    read, and `_beats` only ever compares rungs WITHIN one skill -- so the
    cross-skill buckets do not measure the comparison this numerator is used
    for.

    The `wanted` tie-break is spelled as two `and`/`not` branches rather than
    `if c.wanted != best.wanted: return c.wanted`: the extractor's v1 subset
    rejects `!=` on `Bool`, and this is the shape this function already
    extracted for two years. Semantically identical.

    WANTED IS SPELLED AS A MARGINAL-COST CREDIT AND BEHAVES AS A PIVOT. A rung
    the objective already wants is work the character owes regardless of the
    grind, so the grind's marginal cost for it is zero — hence
    `effective_steps = 0` rather than a key above the rate. Crafting a wanted
    item gains the SAME skill xp and yields a keeper instead of a throwaway
    (2026-06-24: pure cheapest-chain greed made the bot craft a value-10
    `apprentice_gloves` while ignoring the committed value-83 `copper_dagger`).
    It keeps every term in one currency, which is the argument
    `ai/skill_grind_cost_core` already makes.

    What it does NOT do is make a wanted rung win on merit rather than by
    fiat — this docstring said so until 2026-08-15 and the design discussion
    chose the credit over a lexicographic pivot partly on that claim. Swept
    exhaustively over the domain this core can be handed (`craft_level` 1..11 ×
    `acquire_steps` 0..11 on BOTH sides, 17424 ordered pairs): a wanted
    challenger beats an unwanted incumbent in 17424 of 17424, and an unwanted
    challenger beats a wanted incumbent in 0 of 17424. `_beats(wanted level 1 /
    500 steps, unwanted level 5 / 2 steps)` is True — the very outcome the
    pivot was rejected for producing, and
    `test_a_wanted_rung_wins_on_rate_because_its_chain_is_owed_anyway` pins
    those literal numbers. The Lean role theorem `beats_prefers_wanted` proves
    it with NO rate hypothesis at all, only `0 ≤ craft_level` and
    `0 ≤ acquire_steps`: crediting the challenger to zero makes the incumbent's
    cross product zero, and a product of two nonnegatives cannot lose to zero.
    `wanted` is a total pivot here, exactly as the rejected option would have
    been.

    THE ONE BEHAVIOURAL DIFFERENCE FROM THAT PIVOT IS AMONG WANTED RUNGS.
    Compared against `wanted` as a lexicographic key above this same rate, over
    the same 17424-pair domain, the two orderings agree on every
    unwanted-vs-unwanted, wanted-vs-unwanted and unwanted-vs-wanted pair and
    differ only on wanted-vs-wanted ones (4136 of 17424): the credit ties every
    wanted rung's rate at zero, so `craft_level` decides and raw `acquire_steps`
    only breaks what is left — `_beats(wanted level 5 / 500 steps, wanted level
    1 / 1 step)` is True — whereas a pivot would have left them ordered by their
    UNCREDITED rate, `craft_level` over real cost. That, and the single-currency
    argument above, is the whole case for the credit; the "wins on merit"
    reading is not part of it.

    WHY THERE ARE STILL TWO TIE-BREAKS UNDER THE CREDIT. Crediting to zero
    makes every wanted rung tie every other wanted rung on rate, which destroys
    the cost signal among them — two rungs both owed are not equally near, so
    RAW `acquire_steps` is the last key. It recovers that signal only at EQUAL
    `craft_level`, since the level tie-break sits above it: `_beats(wanted level
    5 / 500 steps, wanted level 1 / 1 step)` is True. And a free throwaway also credits to
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
