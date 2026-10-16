"""Outils Hue exposés au LLM : état, réglage des lumières et scènes."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from eva.domain import NoArgs, Tool, ToolEffect, ToolError, choice, with_choices
from eva.plugins.hue.client import HueApi, Resource
from eva.plugins.hue.home import HOME_ALIASES, Group, Home, load_home


@dataclass(frozen=True, slots=True)
class ColorPreset:
    payload: Resource


def _xy(x: float, y: float) -> ColorPreset:
    return ColorPreset({"color": {"xy": {"x": x, "y": y}}})


def _kelvin(kelvin: int) -> ColorPreset:
    return ColorPreset({"color_temperature": {"mirek": round(1_000_000 / kelvin)}})


# Liste fermée : un petit modèle choisit bien mieux dans un menu qu'en inventant un code couleur.
COLORS: dict[str, ColorPreset] = {
    "blanc chaud": _kelvin(2700),
    "blanc neutre": _kelvin(4000),
    "blanc froid": _kelvin(6500),
    "rouge": _xy(0.6915, 0.3083),
    "orange": _xy(0.5800, 0.3900),
    "jaune": _xy(0.4432, 0.5154),
    "vert": _xy(0.1700, 0.7000),
    "cyan": _xy(0.1607, 0.3423),
    "bleu": _xy(0.1532, 0.0475),
    "violet": _xy(0.2725, 0.1096),
    "rose": _xy(0.4149, 0.1776),
}

_GROUP_KINDS = {"room": "pièce", "zone": "zone", "home": "maison"}


class HueStatusTool(Tool[NoArgs]):
    name = "hue_status"
    description = (
        "État des lumières Philips Hue : pièces, zones, lampes (allumées ou non, "
        "intensité) et liste des scènes disponibles. À utiliser pour toute question "
        "sur les lumières ou les scènes."
    )
    effect = ToolEffect.READ
    args_model = NoArgs

    def __init__(self, api: HueApi) -> None:
        self._api = api

    async def run(self, args: NoArgs) -> str:
        return format_status(await load_home(self._api))


class SetLightsArgs(BaseModel):
    target: str = Field(description="Lampe, pièce ou zone à régler.")
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

    def __init__(self, api: HueApi, home: Home) -> None:
        self._api = api
        self._home = home
        self.args_model = with_choices(
            SetLightsArgs,
            target=choice(home.target_names(), aliases=HOME_ALIASES),
            color=choice(COLORS),
        )

    async def run(self, args: SetLightsArgs) -> str:
        target = self._home.find_target(args.target)
        if target is None:  # impossible après validation, sauf installation modifiée
            raise ToolError(f"Lampe ou groupe inconnu : {args.target}")

        body = build_state(on=args.on, brightness=args.brightness, color=args.color)
        if isinstance(target, Group):
            await self._api.put("grouped_light", target.grouped_light_id, body)
        else:
            await self._api.put("light", target.id, body)
        return f"{target.name} : {describe_state(body)}."


class SceneArgs(BaseModel):
    scene: str = Field(description="Nom de la scène.")
    group: str | None = Field(
        default=None, description="Pièce ou zone, si la scène existe à plusieurs endroits."
    )


class HueActivateSceneTool(Tool[SceneArgs]):
    name = "hue_activate_scene"
    description = (
        "Active (allume) une scène Philips Hue. Pour lister les scènes, utiliser hue_status."
    )
    effect = ToolEffect.ACTION

    def __init__(self, api: HueApi, home: Home) -> None:
        self._api = api
        self._home = home
        self.args_model = with_choices(
            SceneArgs,
            scene=choice(s.name for s in home.scenes),
            group=choice(s.group_name for s in home.scenes),
        )

    async def run(self, args: SceneArgs) -> str:
        scenes = self._home.find_scenes(args.scene, args.group)
        if not scenes:
            where = f" ({args.group})" if args.group else ""
            raise ToolError(f"Scène introuvable : {args.scene}{where}")
        if len(scenes) > 1:
            places = ", ".join(s.group_name for s in scenes)
            raise ToolError(f"La scène « {args.scene} » existe pour : {places}. Préciser `group`.")
        scene = scenes[0]
        await self._api.put("scene", scene.id, {"recall": {"action": "active"}})
        return f"Scène « {scene.name} » activée ({scene.group_name})."


def build_state(
    *, on: bool | None = None, brightness: int | None = None, color: str | None = None
) -> Resource:
    """Construit le corps de requête Hue ; régler l'intensité ou la couleur allume."""
    if on is False:
        return {"on": {"on": False}}

    body: Resource = {}
    if brightness is not None:
        body["dimming"] = {"brightness": brightness}
    if color is not None:
        body.update(COLORS[color].payload)
    if on is not True and not body:
        raise ToolError("Rien à changer : préciser `on`, `brightness` ou `color`.")
    body["on"] = {"on": True}
    return body


def describe_state(body: Resource) -> str:
    if not body["on"]["on"]:
        return "éteint"
    parts = ["allumé"]
    if "dimming" in body:
        parts.append(f"{body['dimming']['brightness']} %")
    parts.extend(name for name, preset in COLORS.items() if preset.payload.items() <= body.items())
    return ", ".join(parts)


def format_status(home: Home) -> str:
    lines = ["Groupes :"]
    for group in home.groups:
        lit = sum(home.lights[i].on for i in group.light_ids)
        kind = _GROUP_KINDS[group.kind]
        lines.append(f"- {group.name} ({kind}) : {lit}/{len(group.light_ids)} allumée(s)")
    lines.append("Lampes :")
    for light in home.lights.values():
        if light.on:
            level = f", {light.brightness:.0f} %" if light.brightness is not None else ""
            lines.append(f"- {light.name} : allumée{level}")
        else:
            lines.append(f"- {light.name} : éteinte")
    lines.append("Scènes :")
    for group_name in sorted({s.group_name for s in home.scenes}):
        names = sorted(s.name for s in home.scenes if s.group_name == group_name)
        lines.append(f"- {group_name} : {', '.join(names)}")
    return "\n".join(lines)


def create_hue_tools(api: HueApi, home: Home) -> list[Tool[Any]]:
    """Outils Hue ; leurs schémas reprennent les noms réels de l'installation."""
    tools: list[Tool[Any]] = [HueStatusTool(api), HueSetLightsTool(api, home)]
    if home.scenes:
        tools.append(HueActivateSceneTool(api, home))
    return tools
