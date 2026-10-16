"""Vue simplifiée de l'installation Hue : lampes, groupes et scènes."""

import asyncio
from dataclasses import dataclass
from typing import Literal

from eva.domain import normalize
from eva.plugins.hue.client import HueApi, Resource

HOME_NAME = "Toute la maison"
HOME_ALIASES = {
    alias: HOME_NAME
    for alias in ("tout", "toutes", "partout", "maison", "toute la maison", "tout le monde")
}


@dataclass(frozen=True, slots=True)
class Light:
    id: str
    name: str
    on: bool
    brightness: float | None


@dataclass(frozen=True, slots=True)
class Group:
    name: str
    kind: Literal["room", "zone", "home"]
    grouped_light_id: str
    light_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Scene:
    id: str
    name: str
    group_name: str


@dataclass(frozen=True, slots=True)
class Home:
    lights: dict[str, Light]
    groups: tuple[Group, ...]
    scenes: tuple[Scene, ...]

    def find_target(self, name: str) -> Light | Group | None:
        """Retrouve une lampe ou un groupe par son nom (casse et accents ignorés)."""
        wanted = normalize(HOME_ALIASES.get(normalize(name), name))
        for group in self.groups:
            if normalize(group.name) == wanted:
                return group
        for light in self.lights.values():
            if normalize(light.name) == wanted:
                return light
        return None

    def find_scenes(self, name: str, group_name: str | None = None) -> list[Scene]:
        return [
            scene
            for scene in self.scenes
            if normalize(scene.name) == normalize(name)
            and (group_name is None or normalize(scene.group_name) == normalize(group_name))
        ]

    def target_names(self) -> list[str]:
        return [g.name for g in self.groups] + [light.name for light in self.lights.values()]


async def load_home(api: HueApi) -> Home:
    """Lit l'état complet de l'installation depuis le bridge (requêtes en parallèle)."""
    raw_lights, rooms, zones, grouped_lights, raw_scenes = await asyncio.gather(
        api.get("light"),
        api.get("room"),
        api.get("zone"),
        api.get("grouped_light"),
        api.get("scene"),
    )

    lights = {
        r["id"]: Light(
            id=r["id"],
            name=r["metadata"]["name"],
            on=r["on"]["on"],
            brightness=r.get("dimming", {}).get("brightness"),
        )
        for r in raw_lights
    }
    # Dans une pièce, les enfants sont des appareils ; une lampe appartient à un appareil.
    light_id_by_device = {
        r["owner"]["rid"]: r["id"] for r in raw_lights if r["owner"]["rtype"] == "device"
    }

    groups: list[Group] = []
    group_name_by_id: dict[str, str] = {}
    sources: tuple[tuple[Literal["room", "zone"], list[Resource]], ...] = (
        ("room", rooms),
        ("zone", zones),
    )
    for kind, resources in sources:
        for r in resources:
            light_ids = tuple(
                light_id_by_device.get(child["rid"], child["rid"])
                for child in r["children"]
                if child["rtype"] in ("device", "light")
            )
            grouped_light = next(s["rid"] for s in r["services"] if s["rtype"] == "grouped_light")
            name = r["metadata"]["name"]
            groups.append(
                Group(name, kind, grouped_light, tuple(i for i in light_ids if i in lights))
            )
            group_name_by_id[r["id"]] = name

    home_grouped_light = next(
        (r["id"] for r in grouped_lights if r["owner"]["rtype"] == "bridge_home"), None
    )
    if home_grouped_light:
        groups.append(Group(HOME_NAME, "home", home_grouped_light, tuple(lights)))

    scenes = tuple(
        Scene(r["id"], r["metadata"]["name"], group_name_by_id.get(r["group"]["rid"], "?"))
        for r in raw_scenes
    )
    return Home(lights=lights, groups=tuple(groups), scenes=scenes)
