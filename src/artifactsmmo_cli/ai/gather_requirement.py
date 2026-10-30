"""A resource's gathering skill and level, mandatory (Task 14f, rulings
T14d-7c and T14f-dead): every resource the API serves names one, so a
resource with none in the catalogue raises. API data or fail.

Its own module, below every reader in the import graph: the planner's gather,
the gather pricers (`attempt_prospecting`), the obtain model's gather gate,
the requirement graph, the skill-gate and skill-credit helpers and the
censuses all read it."""

from typing import Protocol


class SkillCatalogue(Protocol):
    """The one catalogue read this module needs (GameData and the requirement
    graph's catalogue view both provide it)."""

    def resource_skill_level(self, code: str) -> tuple[str, int] | None: ...


def gather_requirement(resource: str, game_data: SkillCatalogue) -> tuple[str, int]:
    """The gathering skill and level `resource` asks. Raises for a resource
    with none in the catalogue."""
    requirement = game_data.resource_skill_level(resource)
    if requirement is None:
        raise ValueError(f"resource {resource!r} has no gathering skill in game data")
    return requirement
