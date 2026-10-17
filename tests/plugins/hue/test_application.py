"""Opérations Hue sur une ou plusieurs maisons."""

import pytest

from eva.plugins.hue.application import HueHomes
from eva.plugins.hue.domain import HueError, LightChange
from fakes_hue import FakeTransport, chalet_bridge, connect, main_bridge


@pytest.fixture
async def bridges() -> tuple[FakeTransport, FakeTransport]:
    return main_bridge(), chalet_bridge()


@pytest.fixture
async def homes(bridges: tuple[FakeTransport, FakeTransport]) -> HueHomes:
    main, chalet = bridges
    return HueHomes([await connect("Maison", main), await connect("Chalet", chalet)])


async def test_unique_name_is_resolved_without_home(
    homes: HueHomes, bridges: tuple[FakeTransport, FakeTransport]
) -> None:
    home, target = await homes.set_lights("salon", LightChange(on=True))

    assert (home.name, target.name) == ("Chalet", "Salon")
    assert bridges[1].puts == [("grouped_light", "cg-salon", {"on": {"on": True}})]
    assert bridges[0].puts == []


async def test_shared_name_requires_home(homes: HueHomes) -> None:
    with pytest.raises(HueError, match="plusieurs maisons : Maison, Chalet"):
        await homes.set_lights("Chambre", LightChange(on=False))

    home, _ = await homes.set_lights("Chambre", LightChange(on=False), home="chalet")
    assert home.name == "Chalet"


async def test_whole_home_alias_is_per_home(homes: HueHomes) -> None:
    with pytest.raises(HueError, match="Précisez la maison"):
        await homes.set_lights("partout", LightChange(on=False))


async def test_empty_change_is_rejected(homes: HueHomes) -> None:
    with pytest.raises(HueError, match="Rien à changer"):
        await homes.set_lights("Salon", LightChange())


async def test_renamed_light_is_found_after_refresh(
    homes: HueHomes, bridges: tuple[FakeTransport, FakeTransport]
) -> None:
    bridges[0].data["light"][1]["metadata"]["name"] = "Lampe de chevet"

    _, target = await homes.set_lights("Lampe de chevet", LightChange(on=True))

    assert target.id == "l2"


async def test_ambiguous_scene_within_a_home_asks_for_group(homes: HueHomes) -> None:
    with pytest.raises(HueError, match="Chambre, TV"):
        await homes.activate_scene("Lecture")

    home, scene = await homes.activate_scene("Lecture", group="TV")
    assert (home.name, scene.id) == ("Maison", "s2")


async def test_group_without_scene_is_explained_not_replaced(
    homes: HueHomes, bridges: tuple[FakeTransport, FakeTransport]
) -> None:
    with pytest.raises(HueError, match="« Ordinateur » n'a aucune scène"):
        await homes.activate_scene("Détente", group="Ordinateur")

    assert bridges[0].puts == []


async def test_scene_missing_from_group_lists_available_ones(homes: HueHomes) -> None:
    with pytest.raises(HueError, match=r"Pas de scène « Détente » pour TV\. .* : Lecture\."):
        await homes.activate_scene("Détente", group="TV")


async def test_area_names_include_areas_without_scenes(homes: HueHomes) -> None:
    assert homes.area_names() == ["Chambre", "TV", "Ordinateur", "Salon"]


async def test_unknown_home_is_reported(homes: HueHomes) -> None:
    with pytest.raises(HueError, match="Maison inconnue"):
        await homes.status("Bureau")


async def test_status_refreshes_selected_homes(homes: HueHomes) -> None:
    statuses = await homes.status()

    assert [home.name for home, _ in statuses] == ["Maison", "Chalet"]
    assert [home.name for home, _ in await homes.status("chalet")] == ["Chalet"]


async def test_names_are_merged_across_homes(homes: HueHomes) -> None:
    assert homes.target_names().count("Chambre") == 1
    assert "Salon" in homes.target_names()
    assert homes.scene_names() == ["Lecture", "Détente", "Veillée"]
