"""Contrat que tout fournisseur de LLM doit respecter."""

from collections.abc import Callable, Sequence
from typing import Protocol

from eva.llm.types import Completion, Message, ToolSpec

type TextCallback = Callable[[str], None]
"""Reçoit le texte de la réponse au fil de sa génération (streaming)."""


class LLMError(Exception):
    """Erreur d'un fournisseur de LLM, sans dépendance au SDK sous-jacent."""


class LLMProvider(Protocol):
    """Un LLM capable de répondre à une conversation et d'appeler des outils."""

    @property
    def name(self) -> str: ...

    def complete(
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
            LLMError: en cas d'échec (réseau, modèle absent…).
        """
        ...
