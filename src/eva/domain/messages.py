"""Messages d'une conversation, indépendants de tout fournisseur de LLM."""

from dataclasses import dataclass
from typing import Any


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
