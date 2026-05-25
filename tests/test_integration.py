"""Integration tests for the ArtifactsMMO CLI command surface.

These exercise the real command functions end-to-end
(``list_items``, ``list_monsters``, ``list_resources``, ``list_npcs``,
``list_characters``, ``show_path_command``) and the ``ClientManager``
plumbing. Only the HTTP boundary is mocked: the generated
``artifactsmmo_api_client`` ``.sync`` functions return real schema objects,
and every assertion is made against the rendered console output or the real
return values of the code under test.

The tests run fully offline as part of the normal ``uv run pytest`` run:
no token file, no environment variable, and no network access are required.
They keep the ``@pytest.mark.integration`` marker so they can still be
selected with ``-m integration`` when desired.
"""

import attr
import pytest
from artifactsmmo_api_client.models.character_schema import CharacterSchema
from artifactsmmo_api_client.models.character_skin import CharacterSkin
from artifactsmmo_api_client.models.item_schema import ItemSchema
from artifactsmmo_api_client.models.map_layer import MapLayer
from artifactsmmo_api_client.models.monster_schema import MonsterSchema
from artifactsmmo_api_client.models.my_characters_list_schema import MyCharactersListSchema
from artifactsmmo_api_client.models.resource_schema import ResourceSchema
from artifactsmmo_api_client.models.static_data_page_item_schema import StaticDataPageItemSchema
from artifactsmmo_api_client.models.static_data_page_map_schema import StaticDataPageMapSchema
from artifactsmmo_api_client.models.static_data_page_monster_schema import StaticDataPageMonsterSchema
from artifactsmmo_api_client.models.static_data_page_resource_schema import StaticDataPageResourceSchema
from artifactsmmo_api_client.models.status_response_schema import StatusResponseSchema
from artifactsmmo_api_client.models.status_schema import StatusSchema
from rich.console import Console

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.commands.action import show_path_command
from artifactsmmo_cli.commands.character import list_characters
from artifactsmmo_cli.commands.info import (
    list_items,
    list_monsters,
    list_npcs,
    list_resources,
)
from artifactsmmo_cli.config import Config


def _make_character(name: str = "Hero", level: int = 10, hp: int = 200, x: int = 0, y: int = 0) -> CharacterSchema:
    """Build a fully-populated, real CharacterSchema for rendering tests.

    CharacterSchema has 81 required fields. We fill the typed/enum ones
    explicitly and default every remaining str field to "" and int field to 0,
    then override the handful the tests actually assert on.
    """
    enum_values = {"skin": CharacterSkin.MEN1, "layer": MapLayer.OVERWORLD}
    string_values = {"name": name, "account": "test-account", "task_type": ""}

    kwargs: dict[str, object] = {}
    for f in attr.fields(CharacterSchema):
        if f.default is not attr.NOTHING:
            continue
        if f.name in enum_values:
            kwargs[f.name] = enum_values[f.name]
        elif f.name in string_values:
            kwargs[f.name] = string_values[f.name]
        elif f.type is str:
            kwargs[f.name] = ""
        else:
            kwargs[f.name] = 0

    kwargs["level"] = level
    kwargs["hp"] = hp
    kwargs["max_hp"] = hp
    kwargs["gold"] = 1000
    kwargs["x"] = x
    kwargs["y"] = y

    return CharacterSchema(**kwargs)


@pytest.fixture(autouse=True)
def client_manager() -> ClientManager:
    """Initialize the ClientManager singleton with a dummy offline config.

    No TOKEN file is read and no environment variable is consulted. The
    singleton is reset in teardown so other tests start clean.
    """
    manager = ClientManager()
    manager.initialize(Config(token="test-token"))
    yield manager
    ClientManager._instance = None
    ClientManager._client = None
    ClientManager._api = None
    ClientManager._config = None


@pytest.fixture
def captured_console(monkeypatch: pytest.MonkeyPatch):
    """Patch the console in a target module and return its captured output."""

    def _install(module_path: str) -> Console:
        console = Console(width=120)
        monkeypatch.setattr(module_path, console)
        return console

    return _install


@pytest.mark.integration
class TestInfoCommands:
    """Exercise the info command surface with mocked boundary data."""

    def test_info_items_list(self, monkeypatch, capsys, captured_console):
        captured_console("artifactsmmo_cli.commands.info.console")
        page = StaticDataPageItemSchema(
            data=[
                ItemSchema(
                    name="Copper Ore",
                    code="copper_ore",
                    level=1,
                    type_="resource",
                    subtype="mining",
                    description="Raw copper ore mined from rocks.",
                    tradeable=True,
                ),
            ],
            total=1,
            page=1,
            size=10,
            pages=1,
        )
        monkeypatch.setattr(
            "artifactsmmo_api_client.api.items.get_all_items_items_get.sync",
            lambda **kwargs: page,
        )

        list_items(item_code=None, item_type=None, craft_skill=None, craft_level=None, page=1, size=10)

        output = capsys.readouterr().out
        assert "Items" in output
        assert "copper_ore" in output
        assert "Copper Ore" in output
        assert "Error" not in output

    def test_info_items_specific(self, monkeypatch, capsys, captured_console):
        captured_console("artifactsmmo_cli.commands.info.console")
        item = ItemSchema(
            name="Copper Ore",
            code="copper_ore",
            level=1,
            type_="resource",
            subtype="mining",
            description="Raw copper ore mined from rocks.",
            tradeable=True,
        )
        monkeypatch.setattr(
            "artifactsmmo_api_client.api.items.get_item_items_code_get.sync",
            lambda **kwargs: item,
        )

        list_items(item_code="copper_ore", item_type=None, craft_skill=None, craft_level=None, page=1, size=50)

        output = capsys.readouterr().out
        assert "Item: copper_ore" in output
        assert "Copper Ore" in output
        assert "Error" not in output

    def test_info_monsters_list(self, monkeypatch, capsys, captured_console):
        captured_console("artifactsmmo_cli.commands.info.console")
        page = StaticDataPageMonsterSchema(
            data=[
                MonsterSchema(
                    name="Chicken",
                    code="chicken",
                    level=1,
                    type_="chicken",
                    hp=60,
                    attack_fire=0,
                    attack_earth=0,
                    attack_water=0,
                    attack_air=4,
                    res_fire=0,
                    res_earth=0,
                    res_water=0,
                    res_air=0,
                    critical_strike=0,
                    initiative=0,
                    min_gold=0,
                    max_gold=5,
                    drops=[],
                    effects=[],
                ),
            ],
            total=1,
            page=1,
            size=10,
            pages=1,
        )
        monkeypatch.setattr(
            "artifactsmmo_api_client.api.monsters.get_all_monsters_monsters_get.sync",
            lambda **kwargs: page,
        )

        list_monsters(
            monster_code=None, level=None, min_level=None, max_level=None, compare=None, page=1, size=10
        )

        output = capsys.readouterr().out
        assert "Monsters" in output
        assert "chicken" in output
        assert "Chicken" in output
        assert "Error" not in output

    def test_info_monsters_specific(self, monkeypatch, capsys, captured_console):
        captured_console("artifactsmmo_cli.commands.info.console")
        monster = MonsterSchema(
            name="Chicken",
            code="chicken",
            level=1,
            type_="chicken",
            hp=60,
            attack_fire=0,
            attack_earth=0,
            attack_water=0,
            attack_air=4,
            res_fire=0,
            res_earth=0,
            res_water=0,
            res_air=0,
            critical_strike=0,
            initiative=0,
            min_gold=0,
            max_gold=5,
            drops=[],
            effects=[],
        )
        monkeypatch.setattr(
            "artifactsmmo_api_client.api.monsters.get_monster_monsters_code_get.sync",
            lambda **kwargs: monster,
        )

        list_monsters(
            monster_code="chicken", level=None, min_level=None, max_level=None, compare=None, page=1, size=50
        )

        output = capsys.readouterr().out
        assert "Monster: chicken" in output
        assert "Chicken" in output
        assert "Error" not in output

    def test_info_resources_list(self, monkeypatch, capsys, captured_console):
        captured_console("artifactsmmo_cli.commands.info.console")
        page = StaticDataPageResourceSchema(
            data=[
                ResourceSchema(name="Copper Rocks", code="copper_rock", skill="mining", level=1, drops=[]),
            ],
            total=1,
            page=1,
            size=10,
            pages=1,
        )
        monkeypatch.setattr(
            "artifactsmmo_api_client.api.resources.get_all_resources_resources_get.sync",
            lambda **kwargs: page,
        )

        list_resources(
            resource_code=None,
            skill=None,
            level=None,
            max_level=None,
            resource_type=None,
            location=None,
            radius=None,
            character=None,
            page=1,
            size=10,
        )

        output = capsys.readouterr().out
        assert "Resources" in output
        assert "copper_rock" in output
        assert "Copper Rocks" in output
        assert "Error" not in output

    def test_info_resources_specific(self, monkeypatch, capsys, captured_console):
        captured_console("artifactsmmo_cli.commands.info.console")
        resource = ResourceSchema(name="Copper Rocks", code="copper_rock", skill="mining", level=1, drops=[])
        monkeypatch.setattr(
            "artifactsmmo_api_client.api.resources.get_resource_resources_code_get.sync",
            lambda **kwargs: resource,
        )

        list_resources(
            resource_code="copper_rock",
            skill=None,
            level=None,
            max_level=None,
            resource_type=None,
            location=None,
            radius=None,
            character=None,
            page=1,
            size=50,
        )

        output = capsys.readouterr().out
        assert "Resource: copper_rock" in output
        assert "Copper Rocks" in output
        assert "Error" not in output

    def test_info_npcs_list_reports_no_content(self, monkeypatch, capsys, captured_console):
        """Real MapSchema objects carry no NPC content tiles.

        With genuine schema data (which has no ``content`` attribute) the
        command honestly reports that no NPC content was found rather than
        fabricating a fallback table (CLAUDE.md: use only API data or fail).
        """
        captured_console("artifactsmmo_cli.commands.info.console")
        page = StaticDataPageMapSchema(data=[], total=0, page=1, size=100, pages=1)
        monkeypatch.setattr(
            "artifactsmmo_api_client.api.maps.get_all_maps_maps_get.sync",
            lambda **kwargs: page,
        )

        list_npcs(npc_type=None, page=1, size=10)

        output = capsys.readouterr().out
        assert "No NPC content data found in map API" in output


@pytest.mark.integration
class TestCharacterCommands:
    """Exercise the character command surface with mocked boundary data."""

    def test_character_list(self, monkeypatch, capsys, captured_console):
        captured_console("artifactsmmo_cli.commands.character.console")
        characters = MyCharactersListSchema(data=[_make_character(name="Hero", level=12, hp=180, x=2, y=3)])
        monkeypatch.setattr(
            "artifactsmmo_cli.api_wrapper.get_my_characters_sync",
            lambda **kwargs: characters,
        )

        list_characters()

        output = capsys.readouterr().out
        assert "Characters" in output
        assert "Hero" in output
        assert "12" in output
        assert "180" in output

    def test_character_list_empty(self, monkeypatch, capsys, captured_console):
        captured_console("artifactsmmo_cli.commands.character.console")
        characters = MyCharactersListSchema(data=[])
        monkeypatch.setattr(
            "artifactsmmo_cli.api_wrapper.get_my_characters_sync",
            lambda **kwargs: characters,
        )

        list_characters()

        output = capsys.readouterr().out
        assert "No characters found" in output


@pytest.mark.integration
class TestActionCommands:
    """Exercise the path/pathfinding command surface with mocked boundary data."""

    def test_action_path_calculation(self, monkeypatch, capsys, captured_console):
        captured_console("artifactsmmo_cli.commands.action.console")
        monkeypatch.setattr(
            "artifactsmmo_cli.commands.action.get_character_position",
            lambda character: (0, 0),
        )

        show_path_command(character="Hero", destination="5 5", y=None)

        output = capsys.readouterr().out
        assert "Path for Hero" in output
        assert "From: (0, 0)" in output and "To: (5, 5)" in output
        assert "Total distance: 10" in output

    def test_action_path_already_at_destination(self, monkeypatch, capsys, captured_console):
        captured_console("artifactsmmo_cli.commands.action.console")
        monkeypatch.setattr(
            "artifactsmmo_cli.commands.action.get_character_position",
            lambda character: (5, 5),
        )

        show_path_command(character="Hero", destination="5 5", y=None)

        output = capsys.readouterr().out
        assert "Path for Hero" in output
        assert "already at the destination" in output


@pytest.mark.integration
class TestAPIConnectivity:
    """Exercise ClientManager plumbing and the authenticated boundary calls."""

    def test_client_manager_initialization(self, client_manager):
        assert client_manager.is_initialized()
        assert client_manager.api is not None
        assert client_manager.client is not None
        assert client_manager.config.token == "test-token"

    def test_api_server_status(self, monkeypatch, client_manager):
        status = StatusResponseSchema(
            data=StatusSchema(
                version="1.0",
                server_time="2026-05-25T00:00:00Z",
                max_level=40,
                max_skill_level=40,
                characters_online=42,
                rate_limits=[],
                season=[],
            )
        )
        monkeypatch.setattr(
            "artifactsmmo_cli.api_wrapper.get_server_details_sync",
            lambda **kwargs: status,
        )

        response = client_manager.api.get_server_details()

        assert response is not None
        assert response.data is not None
        assert response.data.version == "1.0"
        assert response.data.max_level == 40

    def test_api_authentication(self, monkeypatch, client_manager):
        characters = MyCharactersListSchema(data=[_make_character(name="Hero")])
        monkeypatch.setattr(
            "artifactsmmo_cli.api_wrapper.get_my_characters_sync",
            lambda **kwargs: characters,
        )

        response = client_manager.api.get_my_characters()

        assert response is not None
        assert response.data is not None
        assert response.data[0].name == "Hero"
