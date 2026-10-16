"""Configuration : la structure dans `eva.toml`, les secrets dans `.env`.

Le cœur ne valide que ses propres réglages. Les sections `[llm.<fournisseur>]` et
`[plugins.<nom>]` restent brutes : chaque composant valide la sienne, si bien que le
cœur n'a pas à connaître le schéma des plugins.
"""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

DEFAULT_CONFIG_PATH = Path("eva.toml")
DEFAULT_SECRETS_PATH = Path(".env")


def config_path() -> Path:
    """Fichier de configuration : `EVA_CONFIG` ou `eva.toml` dans le dossier courant."""
    return Path(os.environ.get("EVA_CONFIG") or DEFAULT_CONFIG_PATH)


class _Sections(BaseModel):
    """Section dont les sous-tables sont réservées à d'autres composants."""

    model_config = ConfigDict(extra="allow")

    def section(self, name: str) -> dict[str, Any]:
        """Sous-table brute `name`, ou `{}` si elle est absente."""
        value = (self.model_extra or {}).get(name, {})
        if not isinstance(value, dict):
            raise ValueError(f"La section « {name} » doit être une table TOML.")
        return value


class LlmSettings(_Sections):
    """Section `[llm]` ; `[llm.<fournisseur>]` appartient au fournisseur."""

    provider: str | None = None
    model: str | None = None
    """Modèle à utiliser ; à défaut, celui recommandé par le fournisseur."""
    max_tokens: int = Field(default=1024, gt=0)


class PluginsSettings(_Sections):
    """Section `[plugins]` ; `[plugins.<nom>]` appartient au plugin."""

    enabled: list[str] | None = None
    """Plugins activés ; à défaut, tous."""


class EvaSettings(BaseSettings):
    """Réglages du cœur, lus dans `eva.toml`.

    Toute valeur peut être surchargée par l'environnement : `EVA_LOG_LEVEL=INFO`,
    `EVA_LLM__MODEL=…` (double soulignement pour une sous-section).
    """

    model_config = SettingsConfigDict(
        env_prefix="EVA_",
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
    )

    user_name: str = "Tristan"
    history_turns: int = Field(default=20, gt=0)
    """Nombre d'échanges conservés dans la conversation."""
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "WARNING"
    llm: LlmSettings = Field(default_factory=LlmSettings)
    plugins: PluginsSettings = Field(default_factory=PluginsSettings)

    @field_validator("log_level", mode="before")
    @classmethod
    def _uppercase_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Priorité décroissante ; `.env` est réservé aux secrets (voir `Secrets`).
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls, toml_file=config_path()),
        )


class Secrets:
    """Secrets (clés d'API, jetons…), lus dans l'environnement puis dans `.env`.

    Point d'accès unique : on pourra le brancher plus tard sur le trousseau du système.
    """

    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)

    @classmethod
    def load(cls, dotenv_path: Path = DEFAULT_SECRETS_PATH) -> "Secrets":
        from_file = {k: v for k, v in dotenv_values(dotenv_path).items() if v}
        return cls({**from_file, **os.environ})  # l'environnement l'emporte

    def get(self, name: str) -> SecretStr | None:
        value = self._values.get(name)
        return SecretStr(value) if value else None
