"""Client HTTP minimal pour l'API locale CLIP v2 du bridge Hue."""

from typing import Any, Protocol

import httpx

from eva.domain import EvaError

type Resource = dict[str, Any]


class HueError(EvaError):
    """Le bridge est injoignable ou a refusé la requête."""


class HueApi(Protocol):
    async def get(self, resource_type: str) -> list[Resource]: ...

    async def put(self, resource_type: str, resource_id: str, body: Resource) -> None: ...


class HueClient:
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
