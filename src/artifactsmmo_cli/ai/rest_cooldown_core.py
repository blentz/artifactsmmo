"""The published Rest cooldown, written once.

Rest is the one action whose duration is not roughly constant. Every other
action the planner executes costs about the same wall-clock second whatever its
arguments; a Rest costs one second per one percent of the character's missing hit
points, so the same action can take three seconds or a hundred.

https://docs.artifactsmmo.com/concepts/resting_and_using_items/

That rule was implemented twice, in two units, for two consumers:

* `ai/actions/cost_core.rest_cost_pure` used it correctly, as planner edge cost,
  denominated in a ten-second unit.
* `ai/learning/fight_loop_cost` did NOT use it at all. It charged a flat one
  action per Rest and capped the per-fight figure at one, so a ninety-second
  recovery and a three-second one cost the projection exactly the same.

Both consumers now derive from this function, each dividing by its own declared
seconds-per-unit. Neither restates the formula, so a server rule change is one
edit here rather than a hunt.
"""

REST_MINIMUM_SECONDS = 3
"""Floor the server applies to every Rest, however small the deficit.

Consumables are a flat three seconds regardless of quantity, so this floor is
also the point below which resting stops being the cheaper way to close a
deficit — which is why `rest_cost_pure` had to become deficit-sensitive before
the planner would stop churning potions."""


def rest_cooldown_seconds(missing_hp: int, max_hp: int) -> int:
    """Wall-clock cooldown of one Rest, in whole seconds.

    One second per one percent of missing hit points, rounded UP, with a
    minimum of `REST_MINIMUM_SECONDS`.

    The percentage is computed by integer arithmetic rather than by float
    division and `math.ceil`, so the value is exact at every input and the Lean
    mirror of `rest_cost_pure` can reproduce it without a rounding argument.

    `missing_hp` is clamped into `[0, max_hp]`. The upper clamp is not defensive
    padding: `fight_loop_cost` asks what a Rest costs after a whole CHAIN of
    fights, and a chain's total damage routinely exceeds one bar — the character
    rested part way through. A Rest restores at most a full bar and so can never
    cost more than a hundred seconds.

    `max_hp` must be positive. A character with no hit-point bar is not a state
    this game produces, and dividing by it raises loudly here rather than
    returning a plausible number for an impossible character.
    """
    missing = min(max(0, missing_hp), max_hp)
    percent_ceil = -(-(missing * 100) // max_hp)
    return max(REST_MINIMUM_SECONDS, percent_ceil)
