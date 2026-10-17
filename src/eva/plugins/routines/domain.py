"""Domaine des routines : une routine est une suite d'actions prédéfinies."""

from dataclasses import dataclass, field
from typing import Any

from eva.domain import EvaError


class RoutineError(EvaError):
    """Routine introuvable, mal configurée ou interrompue, avec un message lisible."""


@dataclass(frozen=True, slots=True)
class Step:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Routine:
    name: str
    steps: tuple[Step, ...]
    description: str = ""
