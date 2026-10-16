"""Traduction entre le JSON du bridge et le domaine Hue."""

from eva.plugins.hue.client import HueClient, change_payload
from eva.plugins.hue.domain import WHOLE_HOME, Group, LightChange, WhiteTemperature, XyColor
from fakes_hue import main_bridge


async def test_state_resolves_room_lights_through_devices() -> None:
    state = await HueClient(main_bridge()).fetch_state()

    room = state.find_target("chambre")
    assert isinstance(room, Group)
    assert (room.id, room.kind, room.light_ids) == ("g-room", "room", ("l1", "l2"))
    assert state.find_target("partout") == Group("g-home", WHOLE_HOME, "home", ("l1", "l2"))
    assert [s.group_name for s in state.find_scenes("lecture")] == ["Chambre", "TV"]


async def test_apply_targets_grouped_light_or_light() -> None:
    transport = main_bridge()
    client = HueClient(transport)
    state = await client.fetch_state()

    await client.apply(state.find_target("TV"), LightChange(on=False))  # type: ignore[arg-type]
    await client.apply(state.find_target("Hue Go 1"), LightChange(on=True))  # type: ignore[arg-type]

    assert transport.puts == [
        ("grouped_light", "g-zone", {"on": {"on": False}}),
        ("light", "l2", {"on": {"on": True}}),
    ]


def test_change_payload_translates_colors_and_turns_on() -> None:
    assert change_payload(LightChange(brightness=40, color=WhiteTemperature(2700))) == {
        "on": {"on": True},
        "dimming": {"brightness": 40},
        "color_temperature": {"mirek": 370},
    }
    assert change_payload(LightChange(color=XyColor(0.1, 0.2))) == {
        "on": {"on": True},
        "color": {"xy": {"x": 0.1, "y": 0.2}},
    }


def test_turning_off_wins_over_other_settings() -> None:
    assert change_payload(LightChange(on=False, brightness=80)) == {"on": {"on": False}}
