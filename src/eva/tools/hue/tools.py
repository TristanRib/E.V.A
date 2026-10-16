"""Outils Hue exposés au LLM : état, contrôle et scènes."""

from dataclasses import dataclass
from typing import Any

from eva.llm import ToolEffect, ToolSpec
from eva.tools.hue.client import HueApi, Resource
from eva.tools.hue.home import Group, Home, load_home


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


class HueStatusTool:
    def __init__(self, api: HueApi) -> None:
        self._api = api
        self.spec = ToolSpec(
            name="hue_status",
            description=(
                "État des lumières Philips Hue : pièces, zones, lampes (allumées ou non, "
                "intensité) et liste des scènes disponibles. À utiliser pour toute question "
                "sur les lumières ou les scènes."
            ),
            input_schema={"type": "object", "properties": {}},
            effect=ToolEffect.READ,
        )

    def run(self, arguments: dict[str, Any]) -> str:
        return format_status(load_home(self._api))


class HueControlTool:
    def __init__(self, api: HueApi, home: Home) -> None:
        self._api = api
        self.spec = ToolSpec(
            name="hue_set_lights",
            description=(
                "Allume, éteint ou règle des lumières Philips Hue (une lampe, une pièce, une "
                "zone ou toute la maison). Ne préciser que ce qui doit changer."
            ),
            effect=ToolEffect.ACTION,
            input_schema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": home.target_names(),
                        "description": "Lampe, pièce ou zone à régler.",
                    },
                    "on": {"type": "boolean", "description": "true = allumer, false = éteindre."},
                    "brightness": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Intensité en pourcentage.",
                    },
                    "color": {"type": "string", "enum": list(COLORS), "description": "Couleur."},
                },
                "required": ["target"],
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        home = load_home(self._api)
        target = home.find_target(str(arguments["target"]))
        if target is None:
            raise ValueError(f"Lampe ou groupe inconnu : {arguments['target']}")

        body = build_state(
            on=arguments.get("on"),
            brightness=arguments.get("brightness"),
            color=arguments.get("color"),
        )
        if isinstance(target, Group):
            self._api.put("grouped_light", target.grouped_light_id, body)
        else:
            self._api.put("light", target.id, body)
        return f"{target.name} : {describe_state(body)}."


class HueSceneTool:
    def __init__(self, api: HueApi, home: Home) -> None:
        self._api = api
        scene_groups = sorted({s.group_name for s in home.scenes})
        self.spec = ToolSpec(
            name="hue_activate_scene",
            description=(
                "Active (allume) une scène Philips Hue. Pour lister les scènes, utiliser "
                "hue_status."
            ),
            effect=ToolEffect.ACTION,
            input_schema={
                "type": "object",
                "properties": {
                    "scene": {"type": "string", "enum": sorted({s.name for s in home.scenes})},
                    "group": {
                        "type": "string",
                        "enum": scene_groups,
                        "description": "Pièce ou zone, si la scène existe à plusieurs endroits.",
                    },
                },
                "required": ["scene"],
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        name, group = str(arguments["scene"]), arguments.get("group")
        scenes = load_home(self._api).find_scenes(name, group)
        if not scenes:
            raise ValueError(f"Scène introuvable : {name}" + (f" ({group})" if group else ""))
        if len(scenes) > 1:
            places = ", ".join(s.group_name for s in scenes)
            raise ValueError(f"La scène « {name} » existe pour : {places}. Préciser `group`.")
        scene = scenes[0]
        self._api.put("scene", scene.id, {"recall": {"action": "active"}})
        return f"Scène « {scene.name} » activée ({scene.group_name})."


def build_state(*, on: object = None, brightness: object = None, color: object = None) -> Resource:
    """Construit le corps de requête Hue ; régler l'intensité ou la couleur allume."""
    if on is False:
        return {"on": {"on": False}}

    body: Resource = {}
    if brightness is not None:
        if not isinstance(brightness, int | float) or not 1 <= brightness <= 100:
            raise ValueError("`brightness` doit être un entier entre 1 et 100.")
        body["dimming"] = {"brightness": brightness}
    if color is not None:
        if color not in COLORS:
            raise ValueError(f"Couleur inconnue : {color}. Choix : {', '.join(COLORS)}.")
        body.update(COLORS[str(color)].payload)
    if on is not True and not body:
        raise ValueError("Rien à changer : préciser `on`, `brightness` ou `color`.")
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
        lines.append(
            f"- {group.name} ({_GROUP_KINDS[group.kind]}) : {lit}/{len(group.light_ids)} allumée(s)"
        )
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


def create_hue_tools(api: HueApi) -> list[HueStatusTool | HueControlTool | HueSceneTool]:
    """Crée les outils Hue ; les schémas reprennent les noms réels de l'installation."""
    home = load_home(api)
    return [HueStatusTool(api), HueControlTool(api, home), HueSceneTool(api, home)]
