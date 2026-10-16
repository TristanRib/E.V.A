"""Opérations Hue sur une ou plusieurs maisons, utilisables sans LLM."""

import asyncio
from collections.abc import Callable, Iterable, Sequence

from eva.domain import normalize
from eva.plugins.hue.client import HueClient
from eva.plugins.hue.domain import BridgeState, HueError, LightChange, Scene, Target


class HueHome:
    """Une maison configurée : son bridge et l'état de celui-ci, gardé en cache."""

    def __init__(self, name: str, client: HueClient, state: BridgeState) -> None:
        self.name = name
        self._client = client
        self._state = state

    @classmethod
    async def connect(cls, name: str, client: HueClient) -> "HueHome":
        return cls(name, client, await client.fetch_state())

    @property
    def state(self) -> BridgeState:
        """Dernier état connu (peut dater du démarrage ; voir `refresh`)."""
        return self._state

    async def refresh(self) -> BridgeState:
        self._state = await self._client.fetch_state()
        return self._state

    async def set_lights(self, target: Target, change: LightChange) -> None:
        await self._client.apply(target, change)

    async def activate_scene(self, scene: Scene) -> None:
        await self._client.recall(scene)


class HueHomes:
    """Toutes les maisons ; résout chaque demande vers la bonne maison et le bon élément."""

    def __init__(self, homes: Sequence[HueHome]) -> None:
        if not homes:
            raise ValueError("Au moins une maison est nécessaire.")
        self._homes = tuple(homes)

    @property
    def names(self) -> list[str]:
        return [home.name for home in self._homes]

    @property
    def is_multi(self) -> bool:
        return len(self._homes) > 1

    def target_names(self) -> list[str]:
        return _unique(name for home in self._homes for name in home.state.target_names())

    def scene_names(self) -> list[str]:
        return _unique(s.name for home in self._homes for s in home.state.scenes)

    def scene_groups(self) -> list[str]:
        return _unique(s.group_name for home in self._homes for s in home.state.scenes)

    async def status(self, home: str | None = None) -> list[tuple[HueHome, BridgeState]]:
        """État à jour de la maison demandée, ou de toutes."""
        homes = self._select(home)
        states = await asyncio.gather(*(h.refresh() for h in homes))
        return list(zip(homes, states, strict=True))

    async def set_lights(
        self, target_name: str, change: LightChange, home: str | None = None
    ) -> tuple[HueHome, Target]:
        if change.is_empty:
            raise HueError("Rien à changer : préciser l'allumage, l'intensité ou la couleur.")

        def find(state: BridgeState) -> list[Target]:
            target = state.find_target(target_name)
            return [target] if target is not None else []

        owner, target = await self._resolve(home, find, f"« {target_name} »")
        await owner.set_lights(target, change)
        return owner, target

    async def activate_scene(
        self, scene_name: str, group: str | None = None, home: str | None = None
    ) -> tuple[HueHome, Scene]:
        def find(state: BridgeState) -> list[Scene]:
            scenes = state.find_scenes(scene_name, group)
            if len(scenes) > 1:
                places = ", ".join(s.group_name for s in scenes)
                raise HueError(
                    f"La scène « {scene_name} » existe pour : {places}. Précisez le groupe."
                )
            return scenes

        owner, scene = await self._resolve(home, find, f"la scène « {scene_name} »")
        await owner.activate_scene(scene)
        return owner, scene

    async def _resolve[T](
        self, home: str | None, find: Callable[[BridgeState], list[T]], label: str
    ) -> tuple[HueHome, T]:
        """Trouve l'élément dans la maison demandée, ou dans l'unique maison qui le contient.

        `find` renvoie l'élément trouvé dans une maison (liste vide sinon). Si rien n'est
        trouvé, l'état est rafraîchi une fois (renommage depuis le démarrage).
        """
        homes = self._select(home)
        matches = [(h, item) for h in homes for item in find(h.state)]
        if not matches:
            await asyncio.gather(*(h.refresh() for h in homes))
            matches = [(h, item) for h in homes for item in find(h.state)]

        if not matches:
            where = f" dans « {homes[0].name} »" if home else ""
            raise HueError(f"Introuvable{where} : {label}.")
        if len(matches) > 1:
            names = ", ".join(h.name for h, _ in matches)
            raise HueError(
                f"{label.capitalize()} existe dans plusieurs maisons : {names}. Précisez la maison."
            )
        return matches[0]

    def _select(self, home: str | None) -> list[HueHome]:
        if home is None:
            return list(self._homes)
        selected = [h for h in self._homes if normalize(h.name) == normalize(home)]
        if not selected:
            raise HueError(f"Maison inconnue : {home}. Maisons : {', '.join(self.names)}.")
        return selected


def _unique(values: Iterable[str]) -> list[str]:
    """Valeurs sans doublon, dans l'ordre de première apparition."""
    return list(dict.fromkeys(values))
