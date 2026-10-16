"""Client HTTP minimal pour l'API locale CLIP v2 du bridge Hue."""

from typing import Any, Protocol

import httpx

type Resource = dict[str, Any]


class HueError(Exception):
    """Le bridge est injoignable ou a refusé la requête."""


class HueApi(Protocol):
    def get(self, resource_type: str) -> list[Resource]: ...

    def put(self, resource_type: str, resource_id: str, body: Resource) -> None: ...


class HueClient:
    def __init__(self, bridge_ip: str, app_key: str, *, timeout: float = 5.0) -> None:
        self._http = httpx.Client(
            base_url=f"https://{bridge_ip}/clip/v2/resource",
            headers={"hue-application-key": app_key},
            # Certificat auto-signé du bridge : vérification désactivée (réseau local).
            verify=False,
            timeout=timeout,
        )

    def get(self, resource_type: str) -> list[Resource]:
        data: list[Resource] = self._request("GET", f"/{resource_type}")["data"]
        return data

    def put(self, resource_type: str, resource_id: str, body: Resource) -> None:
        self._request("PUT", f"/{resource_type}/{resource_id}", json=body)

    def _request(self, method: str, path: str, json: Resource | None = None) -> Resource:
        try:
            response = self._http.request(method, path, json=json)
        except httpx.HTTPError as e:
            raise HueError(f"Bridge Hue injoignable : {e}") from e
        try:
            payload: Resource = response.json()
        except ValueError as e:
            raise HueError(f"Réponse illisible du bridge (HTTP {response.status_code})") from e
        if errors := payload.get("errors"):
            raise HueError("; ".join(e["description"] for e in errors))
        if response.is_error:
            raise HueError(f"Erreur du bridge (HTTP {response.status_code})")
        return payload
