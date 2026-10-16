"""Configuration, lue depuis l'environnement et le fichier `.env`.

Chaque composant (cœur, fournisseur de LLM, plugin) déclare ses propres réglages en
héritant de `EvaBaseSettings` : le cœur n'a pas à connaître ceux des plugins.
"""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EvaBaseSettings(BaseSettings):
    """Base commune : lecture de `.env`, valeurs vides = non renseignées."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # `EVA_MODEL=` vaut « non renseigné », pas une chaîne vide
        extra="ignore",
        # Sans cela, `OllamaSettings(context_size=…)` serait ignoré en silence : seul
        # l'alias (`OLLAMA_CONTEXT_SIZE`) serait accepté.
        validate_by_name=True,
    )


class EvaSettings(EvaBaseSettings):
    """Réglages du cœur d'E.V.A."""

    # --- LLM ---
    provider: str | None = Field(default=None, validation_alias="EVA_PROVIDER")
    model: str | None = Field(default=None, validation_alias="EVA_MODEL")
    """Modèle à utiliser ; à défaut, celui recommandé par le fournisseur."""
    max_tokens: int = Field(default=1024, gt=0, validation_alias="EVA_MAX_TOKENS")

    # --- Conversation ---
    user_name: str = Field(default="Tristan", validation_alias="EVA_USER_NAME")
    history_turns: int = Field(default=20, gt=0, validation_alias="EVA_HISTORY_TURNS")
    """Nombre d'échanges conservés dans la conversation."""

    # --- Plugins ---
    plugins: str | None = Field(default=None, validation_alias="EVA_PLUGINS")
    """Plugins activés, séparés par des virgules ; à défaut, tous."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="WARNING", validation_alias="EVA_LOG_LEVEL"
    )

    @property
    def enabled_plugins(self) -> frozenset[str] | None:
        if self.plugins is None:
            return None
        return frozenset(name.strip() for name in self.plugins.split(",") if name.strip())

    @field_validator("log_level", mode="before")
    @classmethod
    def _uppercase_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value
