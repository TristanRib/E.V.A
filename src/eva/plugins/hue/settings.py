"""Réglages du plugin Hue (variables `HUE_*`)."""

from pydantic import Field, SecretStr

from eva.config import EvaBaseSettings


class HueSettings(EvaBaseSettings):
    bridge_ip: str | None = Field(default=None, validation_alias="HUE_BRIDGE_IP")
    app_key: SecretStr | None = Field(default=None, validation_alias="HUE_APP_KEY")
    """Clé d'application délivrée par le bridge lors de l'appairage."""
