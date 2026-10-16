"""Outils Hue testés contre un faux bridge (aucun réseau)."""

from typing import Any

import pytest

from eva.llm import ToolEffect
from eva.tools.hue.client import Resource
from eva.tools.hue.home import HOME_NAME, Group, load_home
from eva.tools.hue.tools import (
    HueControlTool,
    HueSceneTool,
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

    def get(self, resource_type: str) -> list[Resource]:
        return self.data[resource_type]

    def put(self, resource_type: str, resource_id: str, body: Resource) -> None:
        self.puts.append((resource_type, resource_id, body))


def run_tool(tool: HueControlTool | HueSceneTool, **arguments: Any) -> str:
    return tool.run(arguments)


def test_rooms_resolve_lights_through_devices() -> None:
    home = load_home(FakeBridge())

    room = home.find_target("chambre")
    assert isinstance(room, Group)
    assert room.light_ids == ("l1", "l2")
    assert home.find_target("partout") == home.groups[-1]
    assert home.groups[-1].name == HOME_NAME


def test_control_room_with_color_and_brightness() -> None:
    bridge = FakeBridge()
    tool = HueControlTool(bridge, load_home(bridge))

    result = run_tool(tool, target="Chambre", brightness=40, color="blanc chaud")

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


def test_control_single_light_off() -> None:
    bridge = FakeBridge()

    run_tool(HueControlTool(bridge, load_home(bridge)), target="hue go 1", on=False)

    assert bridge.puts == [("light", "l2", {"on": {"on": False}})]


def test_build_state_rejects_empty_or_invalid_requests() -> None:
    with pytest.raises(ValueError):
        build_state()
    with pytest.raises(ValueError):
        build_state(brightness=150)
    with pytest.raises(ValueError):
        build_state(color="fuchsia")


def test_ambiguous_scene_asks_for_group() -> None:
    bridge = FakeBridge()
    tool = HueSceneTool(bridge, load_home(bridge))

    with pytest.raises(ValueError, match="Chambre, TV"):
        run_tool(tool, scene="Lecture")
    run_tool(tool, scene="Lecture", group="TV")

    assert bridge.puts == [("scene", "s2", {"recall": {"action": "active"}})]


def test_tool_schemas_list_real_names() -> None:
    _, control, scene = create_hue_tools(FakeBridge())

    assert control.spec.input_schema["properties"]["target"]["enum"] == [
        "Chambre",
        "TV",
        HOME_NAME,
        "Hue Play 1",
        "Hue Go 1",
    ]
    assert scene.spec.input_schema["properties"]["scene"]["enum"] == ["Détente", "Lecture"]


def test_only_status_is_read_only() -> None:
    effects = {tool.spec.name: tool.spec.effect for tool in create_hue_tools(FakeBridge())}

    assert effects == {
        "hue_status": ToolEffect.READ,
        "hue_set_lights": ToolEffect.ACTION,
        "hue_activate_scene": ToolEffect.ACTION,
    }


def test_status_summarizes_groups_lights_and_scenes() -> None:
    status = format_status(load_home(FakeBridge()))

    assert "- Chambre (pièce) : 1/2 allumée(s)" in status
    assert "- Hue Go 1 : éteinte" in status
    assert "- Chambre : Détente, Lecture" in status
