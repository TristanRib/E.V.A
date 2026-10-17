"""Outils Hue pour le LLM : adaptateurs minces vers `HueHomes`, et mise en forme du texte."""

from typing import Any

from pydantic import BaseModel, Field

from eva.domain import Tool, ToolEffect, choice, with_choices
from eva.plugins.hue.application import HueHome, HueHomes
from eva.plugins.hue.domain import (
    PALETTE,
    WHOLE_HOME_ALIASES,
    BridgeState,
    LightChange,
)

_HOME_FIELD = "Maison concernée ; inutile s'il n'y a pas d'ambiguïté."


class StatusArgs(BaseModel):
    home: str | None = Field(default=None, description=_HOME_FIELD)


class HueStatusTool(Tool[StatusArgs]):
    name = "hue_status"
    description = (
        "État des lumières Philips Hue : pièces, zones, lampes (allumées ou non, "
        "intensité) et liste des scènes disponibles. À utiliser pour toute question "
        "sur les lumières ou les scènes."
    )
    effect = ToolEffect.READ

    def __init__(self, homes: HueHomes) -> None:
        self._homes = homes
        self.args_model = with_choices(StatusArgs, home=choice(homes.names))

    async def run(self, args: StatusArgs) -> str:
        statuses = await self._homes.status(args.home)
        if len(statuses) == 1:
            return format_status(statuses[0][1])
        return "\n\n".join(f"## {home.name}\n{format_status(state)}" for home, state in statuses)


class SetLightsArgs(BaseModel):
    target: str = Field(description="Lampe, pièce ou zone à régler.")
    home: str | None = Field(default=None, description=_HOME_FIELD)
    on: bool | None = Field(default=None, description="true = allumer, false = éteindre.")
    brightness: int | None = Field(
        default=None, ge=1, le=100, description="Intensité en pourcentage (1 à 100)."
    )
    color: str | None = Field(default=None, description="Couleur.")


class HueSetLightsTool(Tool[SetLightsArgs]):
    name = "hue_set_lights"
    description = (
        "Allume, éteint ou règle des lumières Philips Hue (une lampe, une pièce, une "
        "zone ou toute la maison). Ne préciser que ce qui doit changer."
    )
    effect = ToolEffect.ACTION

    def __init__(self, homes: HueHomes) -> None:
        self._homes = homes
        self.args_model = with_choices(
            SetLightsArgs,
            target=choice(homes.target_names(), aliases=WHOLE_HOME_ALIASES),
            home=choice(homes.names),
            color=choice(PALETTE),
        )

    async def run(self, args: SetLightsArgs) -> str:
        change = LightChange(
            on=args.on,
            brightness=args.brightness,
            color=PALETTE[args.color] if args.color else None,
        )
        home, target = await self._homes.set_lights(args.target, change, args.home)
        return f"{self._label(target.name, home)} : {describe_change(change, args.color)}."

    def _label(self, name: str, home: HueHome) -> str:
        return f"{name} ({home.name})" if self._homes.is_multi else name


class SceneArgs(BaseModel):
    scene: str = Field(description="Nom de la scène.")
    group: str | None = Field(
        default=None,
        description="Pièce ou zone où activer la scène, si l'utilisateur en précise une.",
    )
    home: str | None = Field(default=None, description=_HOME_FIELD)


class HueActivateSceneTool(Tool[SceneArgs]):
    name = "hue_activate_scene"
    description = (
        "Active (allume) une scène Philips Hue. Pour lister les scènes, utiliser hue_status."
    )
    effect = ToolEffect.ACTION

    def __init__(self, homes: HueHomes) -> None:
        self._homes = homes
        self.args_model = with_choices(
            SceneArgs,
            scene=choice(homes.scene_names()),
            group=choice(homes.area_names()),
            home=choice(homes.names),
        )

    async def run(self, args: SceneArgs) -> str:
        home, scene = await self._homes.activate_scene(args.scene, args.group, args.home)
        place = f"{scene.group_name}, {home.name}" if self._homes.is_multi else scene.group_name
        return f"Scène « {scene.name} » activée ({place})."


def create_hue_tools(homes: HueHomes) -> list[Tool[Any]]:
    """Trois outils quel que soit le nombre de maisons ; noms réels de l'installation."""
    tools: list[Tool[Any]] = [HueStatusTool(homes), HueSetLightsTool(homes)]
    if homes.scene_names():
        tools.append(HueActivateSceneTool(homes))
    return tools


def describe_change(change: LightChange, color_name: str | None) -> str:
    change = change.normalized()
    if not change.on:
        return "éteint"
    parts = ["allumé"]
    if change.brightness is not None:
        parts.append(f"{change.brightness} %")
    if color_name:
        parts.append(color_name)
    return ", ".join(parts)


_GROUP_KINDS = {"room": "pièce", "zone": "zone", "home": "maison"}


def format_status(state: BridgeState) -> str:
    lines = ["Groupes :"]
    for group in state.groups:
        kind = _GROUP_KINDS[group.kind]
        lit = state.lit_count(group)
        lines.append(f"- {group.name} ({kind}) : {lit}/{len(group.light_ids)} allumée(s)")
    lines.append("Lampes :")
    for light in state.lights.values():
        if light.on:
            level = f", {light.brightness:.0f} %" if light.brightness is not None else ""
            lines.append(f"- {light.name} : allumée{level}")
        else:
            lines.append(f"- {light.name} : éteinte")
    lines.append("Scènes :")
    for group_name in sorted({s.group_name for s in state.scenes}):
        names = sorted(s.name for s in state.scenes if s.group_name == group_name)
        lines.append(f"- {group_name} : {', '.join(names)}")
    return "\n".join(lines)
