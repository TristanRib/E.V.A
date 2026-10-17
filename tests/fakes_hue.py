"""Faux bridge Hue : renvoie du JSON au format CLIP v2 et enregistre les écritures."""

from eva.plugins.hue.application import HueHome
from eva.plugins.hue.domain import HueError
from eva.plugins.hue.infrastructure import HueClient, Resource


def light(id: str, name: str, device: str, *, on: bool = True) -> Resource:
    return {
        "id": id,
        "metadata": {"name": name},
        "on": {"on": on},
        "dimming": {"brightness": 50.0},
        "owner": {"rid": device, "rtype": "device"},
    }


def room(id: str, name: str, devices: list[str], grouped_light: str) -> Resource:
    return {
        "id": id,
        "metadata": {"name": name},
        "children": [{"rid": d, "rtype": "device"} for d in devices],
        "services": [{"rid": grouped_light, "rtype": "grouped_light"}],
    }


def scene(id: str, name: str, group: str) -> Resource:
    return {"id": id, "metadata": {"name": name}, "group": {"rid": group}}


class FakeTransport:
    def __init__(self, data: dict[str, list[Resource]], *, down: bool = False) -> None:
        self.data = data
        self.down = down
        self.puts: list[tuple[str, str, Resource]] = []

    async def get(self, resource_type: str) -> list[Resource]:
        if self.down:
            raise HueError("Bridge Hue injoignable (ConnectTimeout)")
        return self.data[resource_type]

    async def put(self, resource_type: str, resource_id: str, body: Resource) -> None:
        if self.down:
            raise HueError("Bridge Hue injoignable (ConnectTimeout)")
        self.puts.append((resource_type, resource_id, body))


def zone(id: str, name: str, lights: list[str], grouped_light: str) -> Resource:
    return {
        "id": id,
        "metadata": {"name": name},
        "children": [{"rid": light_id, "rtype": "light"} for light_id in lights],
        "services": [{"rid": grouped_light, "rtype": "grouped_light"}],
    }


def main_bridge() -> FakeTransport:
    """« Maison » : une chambre (via appareils), une zone TV (via lampes), « Lecture » en double,
    et une zone « Ordinateur » sans aucune scène."""
    return FakeTransport(
        {
            "light": [light("l1", "Hue Play 1", "d1"), light("l2", "Hue Go 1", "d2", on=False)],
            "room": [room("r1", "Chambre", ["d1", "d2"], "g-room")],
            "zone": [
                zone("z1", "TV", ["l1"], "g-zone"),
                zone("z2", "Ordinateur", ["l2"], "g-desk"),
            ],
            "grouped_light": [{"id": "g-home", "owner": {"rid": "b", "rtype": "bridge_home"}}],
            "scene": [
                scene("s1", "Lecture", "r1"),
                scene("s2", "Lecture", "z1"),
                scene("s3", "Détente", "r1"),
            ],
        }
    )


def chalet_bridge() -> FakeTransport:
    """« Chalet » : une chambre (nom partagé avec « Maison ») et un salon (nom unique)."""
    return FakeTransport(
        {
            "light": [light("c1", "Lampe chalet", "cd1"), light("c2", "Applique", "cd2")],
            "room": [
                room("cr1", "Chambre", ["cd1"], "cg-room"),
                room("cr2", "Salon", ["cd2"], "cg-salon"),
            ],
            "zone": [],
            "grouped_light": [{"id": "cg-home", "owner": {"rid": "cb", "rtype": "bridge_home"}}],
            "scene": [scene("cs1", "Veillée", "cr2")],
        }
    )


async def connect(name: str, transport: FakeTransport) -> HueHome:
    return await HueHome.connect(name, HueClient(transport))
