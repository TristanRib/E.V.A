"""Contrat que tout fournisseur de LLM doit respecter."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from eva.domain import AssistantMessage, EvaError, Message, ToolEffect, ToolSpec

type TextCallback = Callable[[str], None]
"""Reçoit le texte de la réponse au fil de sa génération (streaming)."""


class LLMError(EvaError):
    """Échec d'un fournisseur de LLM (réseau, modèle absent…)."""


class StopReason(StrEnum):
    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"


@dataclass(frozen=True, slots=True)
class Completion:
    message: AssistantMessage
    stop_reason: StopReason


class LLMProvider(Protocol):
    """Un LLM capable de répondre à une conversation et d'appeler des outils."""

    @property
    def name(self) -> str: ...

    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        on_text: TextCallback | None = None,
    ) -> Completion:
        """Produit le prochain message de l'assistant.

        Si `on_text` est fourni, il reçoit le texte morceau par morceau pendant la
        génération ; la réponse complète est renvoyée dans tous les cas.

        Raises:
            LLMError: en cas d'échec.
        """
        ...

    async def aclose(self) -> None:
        """Libère les ressources (connexions…)."""
        ...


_EFFECT_TAGS = {
    ToolEffect.READ: "[LECTURE SEULE]",
    ToolEffect.ACTION: "[ACTION : modifie le monde réel]",
}


def describe_tool(spec: ToolSpec) -> str:
    """Description envoyée au LLM, préfixée de l'effet de l'outil.

    Tous les fournisseurs l'utilisent : le prompt système peut ainsi poser une règle
    générique sur les outils `[ACTION]`.
    """
    return f"{_EFFECT_TAGS[spec.effect]} {spec.description}"
