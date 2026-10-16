"""Configuration du plugin Hue : section `[plugins.hue]` d'`eva.toml` + secrets."""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from eva.domain import normalize


class HomeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    """Nom donné à la maison (« Maison », « Chalet »…)."""
    bridge_ip: str


class HueConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    homes: list[HomeConfig] = Field(default_factory=list)

    @field_validator("homes")
    @classmethod
    def _unique_names(cls, homes: list[HomeConfig]) -> list[HomeConfig]:
        names = [normalize(home.name) for home in homes]
        if len(names) != len(set(names)):
            raise ValueError("deux maisons portent le même nom")
        return homes


def key_secret_name(home_name: str) -> str:
    """Nom du secret contenant la clé du bridge : « Chalet d'été » → `HUE_KEY_CHALET_D_ETE`."""
    slug = re.sub(r"[^A-Z0-9]+", "_", normalize(home_name).upper()).strip("_")
    return f"HUE_KEY_{slug}"
