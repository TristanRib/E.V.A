"""Outils Hue testés contre un faux bridge (aucun réseau)."""

from typing import Any

import pytest
from pydantic import ValidationError

from eva.domain import Tool, ToolEffect, ToolError
from eva.plugins.hue.client import Resource
from eva.plugins.hue.home import HOME_NAME, Group, Home, load_home
from eva.plugins.hue.tools import (
    HueActivateSceneTool,
    HueSetLightsTool,
    build_state,
    create_hue_tools,
    format_status,
)


def light(id: str, name: str, device: str, *, on: bool = True) -> Resource:
    return {
        "id": id,
        "metadata": {"name": name},
        "on": {"on": on},
        "dimming": {"brightness": 50.0},
        "owner": {"rid": device, "rtype": "device"},
    }


class FakeBridge:
    """Une chambre (via des appareils), une zone (via des lampes), deux scènes « Lecture »."""

    def __init__(self) -> None:
        self.puts: list[tuple[str, str, Resource]] = []
        self.data: dict[str, list[Resource]] = {
            "light": [light("l1", "Hue Play 1", "d1"), light("l2", "Hue Go 1", "d2", on=False)],
            "room": [
                {
                    "id": "r1",
                    "metadata": {"name": "Chambre"},
                    "children": [
                        {"rid": "d1", "rtype": "device"},
                        {"rid": "d2", "rtype": "device"},
                    ],
                    "services": [{"rid": "g-room", "rtype": "grouped_light"}],
                }
            ],
            "zone": [
                {
                    "id": "z1",
                    "metadata": {"name": "TV"},
                    "children": [{"rid": "l1", "rtype": "light"}],
                    "services": [{"rid": "g-zone", "rtype": "grouped_light"}],
                }
            ],
            "grouped_light": [{"id": "g-home", "owner": {"rid": "b", "rtype": "bridge_home"}}],
            "scene": [
                {"id": "s1", "metadata": {"name": "Lecture"}, "group": {"rid": "r1"}},
                {"id": "s2", "metadata": {"name": "Lecture"}, "group": {"rid": "z1"}},
                {"id": "s3", "metadata": {"name": "Détente"}, "group": {"rid": "r1"}},
            ],
        }

    async def get(self, resource_type: str) -> list[Resource]:
        return self.data[resource_type]

    async def put(self, resource_type: str, resource_id: str, body: Resource) -> None:
        self.puts.append((resource_type, resource_id, body))


@pytest.fixture
def bridge() -> FakeBridge:
    return FakeBridge()


@pytest.fixture
async def home(bridge: FakeBridge) -> Home:
    return await load_home(bridge)


async def run(tool: Tool[Any], **arguments: Any) -> str:
    result: str = await tool.run(tool.parse_args(arguments))
    return result


async def test_rooms_resolve_lights_through_devices(home: Home) -> None:
    room = home.find_target("chambre")

    assert isinstance(room, Group)
    assert room.light_ids == ("l1", "l2")
    assert home.find_target("partout") == home.groups[-1]
    assert home.groups[-1].name == HOME_NAME


async def test_set_room_color_and_brightness(bridge: FakeBridge, home: Home) -> None:
    result = await run(
        HueSetLightsTool(bridge, home), target="chambre", brightness=40, color="Blanc chaud"
    )

    assert bridge.puts == [
        (
            "grouped_light",
            "g-room",
            {
                "dimming": {"brightness": 40},
                "color_temperature": {"mirek": 370},
                "on": {"on": True},
            },
        )
    ]
    assert result == "Chambre : allumé, 40 %, blanc chaud."


async def test_turn_off_single_light(bridge: FakeBridge, home: Home) -> None:
    await run(HueSetLightsTool(bridge, home), target="Hue Go 1", on=False)

    assert bridge.puts == [("light", "l2", {"on": {"on": False}})]


async def test_unknown_target_or_color_is_rejected_before_any_call(
    bridge: FakeBridge, home: Home
) -> None:
    tool = HueSetLightsTool(bridge, home)

    with pytest.raises(ValidationError):
        tool.parse_args({"target": "Cuisine", "on": True})
    with pytest.raises(ValidationError):
        tool.parse_args({"target": "TV", "color": "fuchsia"})
    assert bridge.puts == []


def test_build_state_requires_a_change() -> None:
    with pytest.raises(ToolError):
        build_state()


async def test_ambiguous_scene_asks_for_group(bridge: FakeBridge, home: Home) -> None:
    tool = HueActivateSceneTool(bridge, home)

    with pytest.raises(ToolError, match="Chambre, TV"):
        await run(tool, scene="Lecture")
    await run(tool, scene="lecture", group="TV")

    assert bridge.puts == [("scene", "s2", {"recall": {"action": "active"}})]


async def test_tools_expose_real_names_and_effects(bridge: FakeBridge, home: Home) -> None:
    specs = {tool.spec().name: tool.spec() for tool in create_hue_tools(bridge, home)}

    assert {name: spec.effect for name, spec in specs.items()} == {
        "hue_status": ToolEffect.READ,
        "hue_set_lights": ToolEffect.ACTION,
        "hue_activate_scene": ToolEffect.ACTION,
    }
    assert specs["hue_set_lights"].input_schema["properties"]["target"]["enum"] == [
        "Chambre",
        "TV",
        HOME_NAME,
        "Hue Play 1",
        "Hue Go 1",
    ]
    assert specs["hue_activate_scene"].input_schema["properties"]["scene"]["enum"] == [
        "Lecture",
        "Détente",
    ]


async def test_status_summarizes_groups_lights_and_scenes(home: Home) -> None:
    status = format_status(home)

    assert "- Chambre (pièce) : 1/2 allumée(s)" in status
    assert "- Hue Go 1 : éteinte" in status
    assert "- Chambre : Détente, Lecture" in status
