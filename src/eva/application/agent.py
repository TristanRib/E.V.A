"""Boucle d'agent : message utilisateur → LLM → outils → … → réponse finale."""

from collections.abc import Iterable

from eva.application.conversation import Conversation
from eva.application.events import (
    EventSink,
    FanOut,
    TextDelta,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
)
from eva.application.llm import LLMProvider, StopReason
from eva.application.toolbox import Toolbox
from eva.domain import EvaError, ToolResultsMessage, UserMessage

TRUNCATED_NOTE = "\n[réponse tronquée]"


class AgentError(EvaError):
    """Le tour n'a pas pu aboutir."""


class Agent:
    def __init__(
        self,
        llm: LLMProvider,
        toolbox: Toolbox,
        system_prompt: str,
        conversation: Conversation,
        *,
        max_steps: int = 10,
        observers: Iterable[EventSink] = (),
    ) -> None:
        self._llm = llm
        self._toolbox = toolbox
        self._system_prompt = system_prompt
        self._conversation = conversation
        self._max_steps = max_steps
        self._observers = tuple(observers)

    @property
    def conversation(self) -> Conversation:
        return self._conversation

    async def ask(self, text: str, sink: EventSink | None = None) -> str:
        """Traite un message utilisateur et renvoie la réponse finale d'E.V.A.

        Les événements du tour sont émis vers `sink` et vers les observateurs.
        Le tour est atomique : en cas d'erreur ou d'annulation, la conversation revient
        à son état d'avant le message.

        Raises:
            LLMError: le fournisseur a échoué.
            AgentError: le LLM a dépassé le nombre d'étapes autorisé.
        """
        events = FanOut((*self._observers, *([sink] if sink else [])))
        checkpoint = self._conversation.checkpoint()
        try:
            reply = await self._run_turn(text, events)
        except BaseException:  # y compris annulation (Ctrl+C)
            self._conversation.rollback(checkpoint)
            raise
        self._conversation.trim()
        events.emit(TurnFinished(reply))
        return reply

    async def _run_turn(self, text: str, events: EventSink) -> str:
        self._conversation.append(UserMessage(text))

        for _ in range(self._max_steps):
            completion = await self._llm.complete(
                system=self._system_prompt,
                messages=self._conversation.messages,
                tools=self._toolbox.specs(),
                on_text=lambda chunk: events.emit(TextDelta(chunk)),
            )
            message = completion.message
            self._conversation.append(message)

            match completion.stop_reason:
                case StopReason.TOOL_USE if message.tool_calls:
                    if message.text:
                        events.emit(TextDelta("\n"))  # sépare le préambule de la réponse
                    for call in message.tool_calls:
                        events.emit(ToolCallStarted(call))
                    results = await self._toolbox.execute_all(message.tool_calls)
                    for call, result in zip(message.tool_calls, results, strict=True):
                        events.emit(ToolCallFinished(call, result))
                    self._conversation.append(ToolResultsMessage(results))
                case StopReason.MAX_TOKENS:
                    events.emit(TextDelta(TRUNCATED_NOTE))
                    return message.text + TRUNCATED_NOTE
                case _:
                    return message.text

        raise AgentError(f"Abandon après {self._max_steps} étapes sans réponse finale.")
