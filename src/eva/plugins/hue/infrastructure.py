"""Accès au bridge Hue : seul module qui connaît l'API locale CLIP v2 et son format JSON."""

import asyncio
from typing import Any, Literal, Protocol

import httpx

from eva.plugins.hue.domain import (
    WHOLE_HOME,
    BridgeState,
    Group,
    HueError,
    Light,
    LightChange,
    Scene,
    Target,
    WhiteTemperature,
    XyColor,
)

type Resource = dict[str, Any]


class HueTransport(Protocol):
    """Requêtes brutes vers `/clip/v2/resource` (remplaçable par un faux dans les tests)."""

    async def get(self, resource_type: str) -> list[Resource]: ...

    async def put(self, resource_type: str, resource_id: str, body: Resource) -> None: ...


class HttpTransport:
    def __init__(self, bridge_ip: str, app_key: str, *, timeout: float = 5.0) -> None:
        self._http = httpx.AsyncClient(
            base_url=f"https://{bridge_ip}/clip/v2/resource",
            headers={"hue-application-key": app_key},
            # Certificat auto-signé du bridge : vérification désactivée (réseau local).
            verify=False,
            timeout=timeout,
        )

    async def get(self, resource_type: str) -> list[Resource]:
        data: list[Resource] = (await self._request("GET", f"/{resource_type}"))["data"]
        return data

    async def put(self, resource_type: str, resource_id: str, body: Resource) -> None:
        await self._request("PUT", f"/{resource_type}/{resource_id}", json=body)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, json: Resource | None = None) -> Resource:
        try:
            response = await self._http.request(method, path, json=json)
        except httpx.HTTPError as e:
            # Certaines erreurs httpx (délai dépassé…) n'ont pas de message : on garde leur type.
            detail = str(e) or type(e).__name__
            raise HueError(f"Bridge Hue injoignable ({detail})") from e
        try:
            payload: Resource = response.json()
        except ValueError as e:
            raise HueError(f"Réponse illisible du bridge (HTTP {response.status_code})") from e
        if errors := payload.get("errors"):
            raise HueError("; ".join(e["description"] for e in errors))
        if response.is_error:
            raise HueError(f"Erreur du bridge (HTTP {response.status_code})")
        return payload


class HueClient:
    """Opérations du bridge, exprimées avec les objets du domaine."""

    def __init__(self, transport: HueTransport) -> None:
        self._transport = transport

    async def fetch_state(self) -> BridgeState:
        """Lit lampes, groupes et scènes (requêtes en parallèle)."""
        lights, rooms, zones, grouped_lights, scenes = await asyncio.gather(
            self._transport.get("light"),
            self._transport.get("room"),
            self._transport.get("zone"),
            self._transport.get("grouped_light"),
            self._transport.get("scene"),
        )
        return parse_state(lights, rooms, zones, grouped_lights, scenes)

    async def apply(self, target: Target, change: LightChange) -> None:
        resource_type = "grouped_light" if isinstance(target, Group) else "light"
        await self._transport.put(resource_type, target.id, change_payload(change))

    async def recall(self, scene: Scene) -> None:
        await self._transport.put("scene", scene.id, {"recall": {"action": "active"}})


def parse_state(
    lights: list[Resource],
    rooms: list[Resource],
    zones: list[Resource],
    grouped_lights: list[Resource],
    scenes: list[Resource],
) -> BridgeState:
    parsed_lights = {
        r["id"]: Light(
            id=r["id"],
            name=r["metadata"]["name"],
            on=r["on"]["on"],
            brightness=r.get("dimming", {}).get("brightness"),
        )
        for r in lights
    }
    # Dans une pièce, les enfants sont des appareils ; une lampe appartient à un appareil.
    light_by_device = {
        r["owner"]["rid"]: r["id"] for r in lights if r["owner"]["rtype"] == "device"
    }

    groups: list[Group] = []
    group_names: dict[str, str] = {}
    sources: tuple[tuple[Literal["room", "zone"], list[Resource]], ...] = (
        ("room", rooms),
        ("zone", zones),
    )
    for kind, resources in sources:
        for r in resources:
            light_ids = tuple(
                light_id
                for child in r["children"]
                if child["rtype"] in ("device", "light")
                and (light_id := light_by_device.get(child["rid"], child["rid"])) in parsed_lights
            )
            grouped_light = next(s["rid"] for s in r["services"] if s["rtype"] == "grouped_light")
            groups.append(Group(grouped_light, r["metadata"]["name"], kind, light_ids))
            group_names[r["id"]] = r["metadata"]["name"]

    whole_home = next(
        (r["id"] for r in grouped_lights if r["owner"]["rtype"] == "bridge_home"), None
    )
    if whole_home:
        groups.append(Group(whole_home, WHOLE_HOME, "home", tuple(parsed_lights)))

    parsed_scenes = tuple(
        Scene(r["id"], r["metadata"]["name"], group_names.get(r["group"]["rid"], "?"))
        for r in scenes
    )
    return BridgeState(lights=parsed_lights, groups=tuple(groups), scenes=parsed_scenes)


def change_payload(change: LightChange) -> Resource:
    change = change.normalized()
    body: Resource = {"on": {"on": change.on}}
    if change.brightness is not None:
        body["dimming"] = {"brightness": change.brightness}
    match change.color:
        case XyColor(x=x, y=y):
            body["color"] = {"xy": {"x": x, "y": y}}
        case WhiteTemperature(kelvin=kelvin):
            body["color_temperature"] = {"mirek": round(1_000_000 / kelvin)}
    return body
