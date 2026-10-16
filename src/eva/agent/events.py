"""Événements émis par l'agent pendant un tour.

Les interfaces (terminal, vocal, web…) et la journalisation s'y abonnent via `EventSink`,
sans que l'agent ait à les connaître.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from eva.domain import ToolCall, ToolResult


@dataclass(frozen=True, slots=True)
class TextDelta:
    """Morceau de texte de la réponse, au fil de sa génération."""

    text: str


@dataclass(frozen=True, slots=True)
class ToolCallStarted:
    call: ToolCall


@dataclass(frozen=True, slots=True)
class ToolCallFinished:
    call: ToolCall
    result: ToolResult


@dataclass(frozen=True, slots=True)
class TurnFinished:
    reply: str


type AgentEvent = TextDelta | ToolCallStarted | ToolCallFinished | TurnFinished


class EventSink(Protocol):
    def emit(self, event: AgentEvent) -> None: ...


class FanOut:
    """Diffuse chaque événement à plusieurs destinataires."""

    def __init__(self, sinks: Iterable[EventSink]) -> None:
        self._sinks = tuple(sinks)

    def emit(self, event: AgentEvent) -> None:
        for sink in self._sinks:
            sink.emit(event)


class LoggingSink:
    """Journalise les appels d'outils (visibles avec EVA_LOG_LEVEL=INFO)."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("eva.agent")

    def emit(self, event: AgentEvent) -> None:
        if isinstance(event, ToolCallFinished):
            status = "erreur" if event.result.is_error else "ok"
            self._logger.info(
                "Outil %s(%s) [%s] → %s",
                event.call.name,
                event.call.arguments,
                status,
                event.result.content,
            )
