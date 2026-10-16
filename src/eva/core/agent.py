"""Boucle d'agent : message utilisateur → LLM → outils → … → réponse finale."""

import logging

from eva.llm import (
    LLMProvider,
    Message,
    StopReason,
    TextCallback,
    ToolResultsMessage,
    UserMessage,
)
from eva.tools import ToolRegistry

logger = logging.getLogger(__name__)

TRUNCATED_NOTE = "\n[réponse tronquée]"


class AgentError(Exception):
    """Le tour n'a pas pu aboutir."""


class Agent:
    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        system_prompt: str,
        *,
        max_steps: int = 10,
        max_turns: int = 20,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._system_prompt = system_prompt
        self._max_steps = max_steps
        self._max_turns = max_turns
        self._history: list[Message] = []

    @property
    def history(self) -> tuple[Message, ...]:
        return tuple(self._history)

    def reset(self) -> None:
        self._history.clear()

    def ask(self, text: str, *, on_text: TextCallback | None = None) -> str:
        """Traite un message utilisateur et renvoie la réponse finale d'E.V.A.

        Si `on_text` est fourni, il reçoit le texte au fil de sa génération.
        Le tour est atomique : en cas d'erreur ou d'interruption, l'historique revient
        à son état d'avant le message.

        Raises:
            LLMError: le fournisseur a échoué.
            AgentError: le LLM a dépassé le nombre d'étapes autorisé.
        """
        checkpoint = len(self._history)
        try:
            reply = self._run_turn(text, on_text)
        except BaseException:  # y compris Ctrl+C (KeyboardInterrupt)
            del self._history[checkpoint:]
            raise
        self._trim_history()
        return reply

    def _run_turn(self, text: str, on_text: TextCallback | None) -> str:
        self._history.append(UserMessage(text))

        for _ in range(self._max_steps):
            completion = self._llm.complete(
                system=self._system_prompt,
                messages=self._history,
                tools=self._tools.specs(),
                on_text=on_text,
            )
            message = completion.message
            self._history.append(message)

            match completion.stop_reason:
                case StopReason.TOOL_USE if message.tool_calls:
                    if message.text and on_text:
                        on_text("\n")  # sépare un éventuel préambule de la réponse finale
                    results = tuple(self._tools.execute(call) for call in message.tool_calls)
                    for call, result in zip(message.tool_calls, results, strict=True):
                        logger.info("Outil %s(%s) → %s", call.name, call.arguments, result.content)
                    self._history.append(ToolResultsMessage(results))
                case StopReason.MAX_TOKENS:
                    if on_text:
                        on_text(TRUNCATED_NOTE)
                    return message.text + TRUNCATED_NOTE
                case _:
                    return message.text

        raise AgentError(f"Abandon après {self._max_steps} étapes sans réponse finale.")

    def _trim_history(self) -> None:
        """Ne garde que les `max_turns` derniers échanges.

        On coupe toujours au début d'un échange (message utilisateur), pour ne jamais
        séparer un appel d'outil de son résultat.
        """
        turn_starts = [i for i, m in enumerate(self._history) if isinstance(m, UserMessage)]
        excess = len(turn_starts) - self._max_turns
        if excess > 0:
            del self._history[: turn_starts[excess]]
