"""Configuration d'E.V.A, lue depuis l'environnement et le fichier `.env`."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # `EVA_MODEL=` vaut « non renseigné », pas une chaîne vide
        extra="ignore",
    )

    # --- LLM ---
    provider: str | None = Field(default=None, validation_alias="EVA_PROVIDER")
    model: str | None = Field(default=None, validation_alias="EVA_MODEL")
    """Modèle à utiliser ; à défaut, celui recommandé par le fournisseur."""
    max_tokens: int = Field(default=1024, gt=0, validation_alias="EVA_MAX_TOKENS")
    context_size: int = Field(default=8192, ge=2048, validation_alias="EVA_CONTEXT_SIZE")
    """Fenêtre de contexte, en tokens, pour les LLM locaux (plus grand = plus de VRAM)."""
    keep_alive: str = Field(default="30m", validation_alias="EVA_KEEP_ALIVE")
    """Durée de maintien du modèle local en VRAM après usage (`30m`, `2h`, `-1` = toujours)."""

    # --- Conversation ---
    history_turns: int = Field(default=20, gt=0, validation_alias="EVA_HISTORY_TURNS")
    """Nombre d'échanges conservés dans la conversation."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="WARNING", validation_alias="EVA_LOG_LEVEL"
    )

    # --- Ollama ---
    ollama_host: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_HOST")

    # --- Philips Hue ---
    hue_bridge_ip: str | None = Field(default=None, validation_alias="HUE_BRIDGE_IP")
    hue_app_key: SecretStr | None = Field(default=None, validation_alias="HUE_APP_KEY")

    @field_validator("log_level", mode="before")
    @classmethod
    def _uppercase_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value
