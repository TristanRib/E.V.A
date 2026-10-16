"""Domaine Hue : lampes, groupes, scènes et changements d'état.

Couche pure : aucune requête, aucun format d'API, aucune notion de LLM.
"""

from dataclasses import dataclass
from typing import Literal

from eva.domain import EvaError, normalize


class HueError(EvaError):
    """Échec côté Hue (bridge injoignable, demande ambiguë…), avec un message lisible."""


WHOLE_HOME = "Toute la maison"
"""Nom du groupe qui réunit toutes les lampes d'un bridge."""
WHOLE_HOME_ALIASES = {
    alias: WHOLE_HOME
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
    id: str
    """Identifiant du `grouped_light` qui pilote toutes les lampes du groupe."""
    name: str
    kind: Literal["room", "zone", "home"]
    light_ids: tuple[str, ...]


type Target = Light | Group


@dataclass(frozen=True, slots=True)
class Scene:
    id: str
    name: str
    group_name: str


@dataclass(frozen=True, slots=True)
class BridgeState:
    """Ce que contient un bridge à un instant donné."""

    lights: dict[str, Light]
    groups: tuple[Group, ...]
    scenes: tuple[Scene, ...]

    def find_target(self, name: str) -> Target | None:
        """Lampe ou groupe par son nom (casse, accents et alias de « toute la maison » tolérés)."""
        wanted = normalize(WHOLE_HOME_ALIASES.get(normalize(name), name))
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

    def lit_count(self, group: Group) -> int:
        return sum(self.lights[i].on for i in group.light_ids)


@dataclass(frozen=True, slots=True)
class XyColor:
    """Couleur dans l'espace CIE xy."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class WhiteTemperature:
    """Blanc, défini par sa température de couleur."""

    kelvin: int


type Color = XyColor | WhiteTemperature

PALETTE: dict[str, Color] = {
    "blanc chaud": WhiteTemperature(2700),
    "blanc neutre": WhiteTemperature(4000),
    "blanc froid": WhiteTemperature(6500),
    "rouge": XyColor(0.6915, 0.3083),
    "orange": XyColor(0.5800, 0.3900),
    "jaune": XyColor(0.4432, 0.5154),
    "vert": XyColor(0.1700, 0.7000),
    "cyan": XyColor(0.1607, 0.3423),
    "bleu": XyColor(0.1532, 0.0475),
    "violet": XyColor(0.2725, 0.1096),
    "rose": XyColor(0.4149, 0.1776),
}
"""Couleurs nommées : un petit modèle choisit mieux dans une liste qu'en inventant un code."""


@dataclass(frozen=True, slots=True)
class LightChange:
    """Changement demandé ; `None` = inchangé."""

    on: bool | None = None
    brightness: int | None = None
    """Intensité en pourcentage (1 à 100)."""
    color: Color | None = None

    @property
    def is_empty(self) -> bool:
        return self.on is None and self.brightness is None and self.color is None

    def normalized(self) -> "LightChange":
        """Règle métier : éteindre l'emporte ; régler intensité ou couleur allume."""
        if self.on is False:
            return LightChange(on=False)
        return LightChange(on=True, brightness=self.brightness, color=self.color)
