"""Configuration du plugin routines : section `[[plugins.routines.routine]]` d'`eva.toml`."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from eva.domain import normalize


class StepConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str = Field(min_length=1)
    """Nom de l'outil à appeler."""
    args: dict[str, Any] = Field(default_factory=dict)


class RoutineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = ""
    """Montrée au LLM pour reconnaître la routine : ce qu'elle fait, autres noms éventuels."""
    steps: list[StepConfig] = Field(min_length=1)
    """Actions exécutées dans l'ordre."""


class RoutinesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routine: list[RoutineConfig] = Field(default_factory=list)

    @field_validator("routine")
    @classmethod
    def _unique_names(cls, routines: list[RoutineConfig]) -> list[RoutineConfig]:
        names = [normalize(r.name) for r in routines]
        if len(names) != len(set(names)):
            raise ValueError("deux routines portent le même nom")
        return routines
