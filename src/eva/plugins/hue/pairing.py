"""Appairage avec le bridge Hue : `uv run eva-hue-pair`.

Le bridge ne délivre une clé d'application que dans les 30 secondes qui suivent un
appui sur son bouton physique. La clé obtenue est enregistrée dans `.env`.
"""

import time
from pathlib import Path

import httpx

from eva.plugins.hue.settings import HueSettings

DISCOVERY_URL = "https://discovery.meethue.com"
PAIRING_TIMEOUT_S = 30
_LINK_BUTTON_NOT_PRESSED = 101


class PairingError(Exception):
    pass


def discover_bridge_ip() -> str:
    """Trouve l'IP du bridge via le service de découverte de Philips."""
    try:
        bridges = httpx.get(DISCOVERY_URL, timeout=10).raise_for_status().json()
    except httpx.HTTPError as e:
        raise PairingError(f"Découverte du bridge impossible : {e}") from e
    if not bridges:
        raise PairingError("Aucun bridge Hue trouvé sur le réseau.")
    return str(bridges[0]["internalipaddress"])


def request_app_key(bridge_ip: str, *, timeout_s: float = PAIRING_TIMEOUT_S) -> str:
    """Demande une clé au bridge, en réessayant jusqu'à l'appui sur le bouton."""
    deadline = time.monotonic() + timeout_s
    # Certificat auto-signé du bridge : vérification désactivée (trafic limité au réseau local).
    with httpx.Client(verify=False, timeout=5) as client:
        while time.monotonic() < deadline:
            response = client.post(
                f"https://{bridge_ip}/api",
                json={"devicetype": "eva#assistant"},
            )
            result = response.raise_for_status().json()[0]
            if "success" in result:
                return str(result["success"]["username"])
            if result["error"]["type"] != _LINK_BUTTON_NOT_PRESSED:
                raise PairingError(f"Refus du bridge : {result['error']['description']}")
            time.sleep(1)
    raise PairingError("Bouton non pressé à temps. Relancez la commande et réessayez.")


def update_env_file(path: Path, values: dict[str, str]) -> None:
    """Remplace (ou ajoute) les variables données dans un fichier `.env`."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    lines.extend(f"{key}={value}" for key, value in remaining.items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    settings = HueSettings()
    try:
        bridge_ip = settings.bridge_ip or discover_bridge_ip()
        print(f"Bridge Hue : {bridge_ip}")
        print(f"→ Appuyez sur le bouton rond du bridge (vous avez {PAIRING_TIMEOUT_S} s)…")
        app_key = request_app_key(bridge_ip)
    except (PairingError, httpx.HTTPError) as e:
        raise SystemExit(f"[hue] {e}") from e

    update_env_file(Path(".env"), {"HUE_BRIDGE_IP": bridge_ip, "HUE_APP_KEY": app_key})
    print("Appairage réussi : HUE_BRIDGE_IP et HUE_APP_KEY enregistrés dans .env.")


if __name__ == "__main__":
    main()
