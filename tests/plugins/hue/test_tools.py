"""Outils Hue côté LLM : schémas, validation et texte produit."""

from typing import Any

import pytest
from pydantic import ValidationError

from eva.domain import Tool, ToolEffect
from eva.plugins.hue.service import HueHomes
from eva.plugins.hue.tools import create_hue_tools
from fakes_hue import chalet_bridge, connect, main_bridge


async def single_home() -> HueHomes:
    return HueHomes([await connect("Maison", main_bridge())])


async def two_homes() -> HueHomes:
    return HueHomes(
        [await connect("Maison", main_bridge()), await connect("Chalet", chalet_bridge())]
    )


def by_name(tools: list[Tool[Any]]) -> dict[str, Tool[Any]]:
    return {tool.name: tool for tool in tools}


async def run(tool: Tool[Any], **arguments: Any) -> str:
    result: str = await tool.run(tool.parse_args(arguments))
    return result


async def test_three_tools_with_declared_effects() -> None:
    tools = by_name(create_hue_tools(await two_homes()))

    assert {name: tool.effect for name, tool in tools.items()} == {
        "hue_status": ToolEffect.READ,
        "hue_set_lights": ToolEffect.ACTION,
        "hue_activate_scene": ToolEffect.ACTION,
    }


async def test_schema_lists_real_names_and_homes() -> None:
    properties = (
        by_name(create_hue_tools(await two_homes()))["hue_set_lights"]
        .spec()
        .input_schema["properties"]
    )

    assert "Salon" in properties["target"]["enum"]
    assert properties["home"]["enum"] == ["Maison", "Chalet"]
    assert "blanc chaud" in properties["color"]["enum"]


async def test_set_lights_describes_change_single_home() -> None:
    tool = by_name(create_hue_tools(await single_home()))["hue_set_lights"]

    assert await run(tool, target="chambre", brightness=40, color="Blanc chaud") == (
        "Chambre : allumé, 40 %, blanc chaud."
    )


async def test_set_lights_names_home_when_several() -> None:
    tool = by_name(create_hue_tools(await two_homes()))["hue_set_lights"]

    assert await run(tool, target="Salon", on=False) == "Salon (Chalet) : éteint."


async def test_unknown_values_are_rejected_before_any_call() -> None:
    tool = by_name(create_hue_tools(await single_home()))["hue_set_lights"]

    with pytest.raises(ValidationError):
        tool.parse_args({"target": "Cuisine", "on": True})
    with pytest.raises(ValidationError):
        tool.parse_args({"target": "TV", "color": "fuchsia"})


async def test_status_has_one_section_per_home() -> None:
    tool = by_name(create_hue_tools(await two_homes()))["hue_status"]

    status = await run(tool)

    assert "## Maison" in status
    assert "## Chalet" in status
    assert "- Chambre (pièce) : 1/2 allumée(s)" in status


async def test_status_single_home_has_no_title() -> None:
    tool = by_name(create_hue_tools(await single_home()))["hue_status"]

    status = await run(tool)

    assert not status.startswith("##")
    assert "- Hue Go 1 : éteinte" in status
    assert "- Chambre : Détente, Lecture" in status
