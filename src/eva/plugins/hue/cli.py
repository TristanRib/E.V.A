"""Appairage d'un bridge Hue : `uv run eva-hue-pair [--name Chalet] [--ip 10.0.0.5]`.

Le bridge ne délivre une clé d'application que dans les 30 secondes qui suivent un appui
sur son bouton physique. La maison est ajoutée à `eva.toml`, la clé à `.env`.
"""

import argparse
import time
from pathlib import Path
from typing import Any

import httpx
import tomlkit

from eva.config import DEFAULT_SECRETS_PATH, config_path
from eva.domain import normalize
from eva.plugins.hue.config import key_secret_name

DISCOVERY_URL = "https://discovery.meethue.com"
PAIRING_TIMEOUT_S = 30
_LINK_BUTTON_NOT_PRESSED = 101


class PairingError(Exception):
    pass


def discover_bridge_ip(exclude: set[str]) -> str:
    """IP d'un bridge du réseau local, de préférence pas encore configuré."""
    try:
        bridges = httpx.get(DISCOVERY_URL, timeout=10).raise_for_status().json()
    except httpx.HTTPError as e:
        raise PairingError(f"Découverte du bridge impossible : {e}") from e
    ips = [str(bridge["internalipaddress"]) for bridge in bridges]
    if not ips:
        raise PairingError("Aucun bridge Hue trouvé sur le réseau.")
    return next((ip for ip in ips if ip not in exclude), ips[0])


def request_app_key(bridge_ip: str, *, timeout_s: float = PAIRING_TIMEOUT_S) -> str:
    """Demande une clé au bridge, en réessayant jusqu'à l'appui sur le bouton."""
    deadline = time.monotonic() + timeout_s
    # Certificat auto-signé du bridge : vérification désactivée (trafic limité au réseau local).
    with httpx.Client(verify=False, timeout=5) as client:
        while time.monotonic() < deadline:
            response = client.post(f"https://{bridge_ip}/api", json={"devicetype": "eva#assistant"})
            result = response.raise_for_status().json()[0]
            if "success" in result:
                return str(result["success"]["username"])
            if result["error"]["type"] != _LINK_BUTTON_NOT_PRESSED:
                raise PairingError(f"Refus du bridge : {result['error']['description']}")
            time.sleep(1)
    raise PairingError("Bouton non pressé à temps. Relancez la commande et réessayez.")


def configured_bridge_ips(path: Path) -> set[str]:
    return {str(home["bridge_ip"]) for home in _homes(_load(path))}


def save_home(path: Path, name: str, bridge_ip: str) -> None:
    """Ajoute ou met à jour une maison dans `eva.toml` (commentaires préservés)."""
    document = _load(path)
    homes = _homes(document)
    for home in homes:
        if normalize(str(home["name"])) == normalize(name):
            home["bridge_ip"] = bridge_ip
            break
    else:
        home = tomlkit.table()
        home["name"] = name
        home["bridge_ip"] = bridge_ip
        homes.append(home)
    path.write_text(tomlkit.dumps(document), encoding="utf-8")


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


def _load(path: Path) -> tomlkit.TOMLDocument:
    return tomlkit.parse(path.read_text(encoding="utf-8")) if path.exists() else tomlkit.document()


def _homes(document: tomlkit.TOMLDocument) -> Any:
    """Tableau `[[plugins.hue.homes]]`, créé au besoin."""
    plugins: Any = document.setdefault("plugins", tomlkit.table(is_super_table=True))
    hue: Any = plugins.setdefault("hue", tomlkit.table(is_super_table=True))
    return hue.setdefault("homes", tomlkit.aot())


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="eva-hue-pair", description="Appaire un bridge Philips Hue."
    )
    parser.add_argument("--name", default="Maison", help="nom de la maison (défaut : Maison)")
    parser.add_argument("--ip", help="IP du bridge (défaut : découverte automatique)")
    args = parser.parse_args()

    config_file = config_path()
    try:
        bridge_ip = args.ip or discover_bridge_ip(exclude=configured_bridge_ips(config_file))
        print(f"Bridge Hue : {bridge_ip} (maison « {args.name} »)")
        print(f"→ Appuyez sur le bouton rond du bridge (vous avez {PAIRING_TIMEOUT_S} s)…")
        app_key = request_app_key(bridge_ip)
    except (PairingError, httpx.HTTPError) as e:
        raise SystemExit(f"[hue] {e}") from e

    secret_name = key_secret_name(args.name)
    save_home(config_file, args.name, bridge_ip)
    update_env_file(DEFAULT_SECRETS_PATH, {secret_name: app_key})
    print(f"Appairage réussi : maison ajoutée à {config_file}, clé enregistrée ({secret_name}).")


if __name__ == "__main__":
    main()
