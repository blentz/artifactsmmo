"""Pure core: carry a measured XP rate from the level it was measured at to the
level it is being used at.

WHY THIS EXISTS. `expected_yield_per_cycle(...).char_xp` reads as "character XP per
cycle for this monster". It is really "character XP per cycle for this monster AT
THE LEVEL THE SAMPLES WERE TAKEN", and `cheapest_path_to_level` used it as though
that qualifier were not there — reusing one rate unchanged at every rung of a walk
that climbs up to 38 levels.

That is not a rounding error, because the game's XP award is a function OF the gap
between the character and the monster. From
`https://docs.artifactsmmo.com/concepts/stats_and_fights/`:

    XP = Round(((monster_level / player_level) * 20 + monster_hp * 0.04)
               * level_penalty * monster_multiplier * wisdom_bonus)

with `level_penalty` a step function of that gap: 100% at or below the monster's
level, 70% at five or more levels above it, and **0% at ELEVEN or more levels
above it** — the kill awards nothing at all. (The published prose says "ten or
more"; it is loose at its own edge. A gap of exactly ten pays, at the 70% rate —
measured over the learning store's 10_857 ok-fights, 372 of them at gap 10 and
every one paying. See `monster_catalog.xp_per_kill` for the table.)

MEASURED, live, 2026-08-09 (`docs/FINDING_learned_rate_launders_grey_penalty.md`).
C3P0 held 100 samples of `green_slime` at 7.0 XP per cycle, taken at character
level 12. `green_slime` is a LEVEL 4 monster: the formula puts its award at 7 XP at
character level 12 and at **0** from level 15 onward. The walk reused the measured
7.0 at every rung from 12 to 49 and so projected reaching level 50 — the terminal
objective — by farming a monster that would award it nothing for 35 of those 38
levels. A trunk that reaches 50 at acquisition cost zero is unbeatable in `J`, and
four of five live characters were sitting on exactly that projection.

R2D2, whose only observation was NEGATIVE and therefore declined, fell through to
the formula branch and correctly reported a wall at level 17. The character that
looked broken was the only honest one.

THE DIRECTION OF SAFETY IS THE OPPOSITE OF THE ACQUISITION BOUND'S. There, an
under-estimate merely wasted a search and an over-estimate discarded a reachable
plan. Here the figure feeds how FAR a candidate is projected to get, and the
objective prefers candidates that get further — so an over-estimate manufactures
reach that does not exist and captures the whole decision, while an under-estimate
only makes the bot buy gear it might have earned for free. Every judgement below
resolves toward NOT over-promising.
"""


def sample_level(levels: list[int]) -> int | None:
    """The single character level a measurement is treated as having been taken at,
    from the levels its aggregated cycles recorded. `None` when none recorded one.

    A RECORDED LEVEL BELOW ONE IS NOT A LEVEL. Characters begin at 1, so the API
    cannot produce a smaller one, and a zero is the absence of a reading rather
    than a reading of zero. It is dropped here, exactly as a missing level is, and
    for the same reason: the mean must not be contaminated by a value that is not
    evidence. Left in, a zero is not merely wrong but UNDEFINED downstream -- the
    published award divides the monster's level by the character's, so a sample
    level of zero has no award at all, neither positive nor non-positive, and the
    two rules that decide those cases both claim it. Excluding it means the only
    levels that reach the mean are ones the game can actually have issued.

    THE MEAN, ROUNDED, WITH TIES GOING DOWN. A tie is not a curiosity here: the
    published award is a STEP function of the level gap, so the two roundings of a
    half-integer mean can land on opposite sides of the grey boundary. One side
    restates the rate by a finite ratio; the other finds a zero award at the sample
    level, returns 0.0 above, and can thereby stop the whole walk. That is the
    widest divergence a tiebreak can carry, and it must not be left to a language's
    default.

    Ties go DOWN because a lower sample level means a HIGHER published award there,
    hence a SMALLER restated rate -- the direction that does not manufacture reach,
    which is the rule this module resolves everything by. Python's built-in `round`
    is half-to-EVEN, so it sends 16.5 down and 17.5 up; that is arbitrary with
    respect to the character and is why it is not used.

    Computed in integers so no binary-float representation can move a tie.
    """
    real = [level for level in levels if level >= 1]
    if not real:
        return None
    doubled = 2 * sum(real) - len(real)
    return -(-doubled // (2 * len(real)))


def rescale_observed_xp(
    observed_rate: float,
    xp_at_observed_level: int,
    xp_at_target_level: int,
) -> float:
    """`observed_rate`, measured where a kill awarded `xp_at_observed_level`,
    restated for a level where the same kill awards `xp_at_target_level`.

    The two XP figures come from the published formula for the SAME monster at two
    character levels, so their ratio is exactly the factor the game applies —
    carrying both the `level_penalty` step and the `monster_level / player_level`
    decay in the base term. The ratio is dimensionless, so the result stays in the
    measured rate's own unit: character XP per executed planner action, whole
    combat loop included. Nothing here converts a unit, which is what lets S-008's
    "same unit before either is used" hold.

    Returns 0.0 — "this monster contributes nothing at that level" — in the two
    cases where no honest scaling exists:

    * `observed_rate <= 0`. A non-positive measured rate is not evidence of a
      positive one. (R2D2's `red_slime` rate is -11.1 over 100 samples, which is
      its own defect: a negative XP rate should not be representable. It is
      declined here rather than laundered into a small positive.)
    * `xp_at_observed_level <= 0`. The formula says the monster awarded nothing at
      the level the samples were taken, yet a positive rate was recorded. The two
      disagree, there is no ratio to take, and the conservative reading is the one
      that does not manufacture reach.

    A zero `xp_at_target_level` needs no special case and deliberately does not get
    one: it IS the grey-mob rule, and the ordinary arithmetic already returns 0.0.
    Special-casing it would only invite the two encodings to drift apart.
    """
    if observed_rate <= 0:
        return 0.0
    if xp_at_observed_level <= 0:
        return 0.0
    return observed_rate * xp_at_target_level / xp_at_observed_level
