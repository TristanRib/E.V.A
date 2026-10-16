"""Types neutres échangés entre E.V.A et n'importe quel fournisseur de LLM.

Aucun type d'un SDK tiers ne doit fuiter hors de `eva.llm` : chaque fournisseur
traduit ces structures vers son propre format, et inversement.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Description d'un outil telle que présentée au LLM."""

    name: str
    description: str
    input_schema: dict[str, Any]
    """Schéma JSON (type `object`) des arguments attendus."""


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Demande d'exécution d'un outil émise par le LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Résultat d'un outil, renvoyé au LLM."""

    call_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class UserMessage:
    text: str


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    text: str
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolResultsMessage:
    results: tuple[ToolResult, ...]


type Message = UserMessage | AssistantMessage | ToolResultsMessage


class StopReason(StrEnum):
    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"


@dataclass(frozen=True, slots=True)
class Completion:
    message: AssistantMessage
    stop_reason: StopReason
