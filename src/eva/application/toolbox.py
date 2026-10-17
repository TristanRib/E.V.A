"""Registre des outils disponibles et exécution des appels du LLM."""

import asyncio
import logging
from collections.abc import Iterable, Sequence
from typing import Any

from pydantic import ValidationError

from eva.domain import EvaError, Tool, ToolCall, ToolEffect, ToolResult, ToolSpec

logger = logging.getLogger(__name__)


class Toolbox:
    def __init__(self, tools: Iterable[Tool[Any]] = ()) -> None:
        self._tools: dict[str, Tool[Any]] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Outil déjà enregistré : {tool.name}")
            self._tools[tool.name] = tool
        # Calculés une fois : un ordre et un contenu stables favorisent le cache du LLM.
        self._specs = [tool.spec() for tool in self._tools.values()]

    def specs(self) -> list[ToolSpec]:
        return list(self._specs)

    async def execute_all(self, calls: Sequence[ToolCall]) -> tuple[ToolResult, ...]:
        """Exécute les appels d'une même réponse ; les résultats suivent l'ordre des appels.

        Des lectures peuvent s'exécuter en parallèle. Dès qu'une action est présente, l'ordre
        fait partie de l'intention (une action peut compléter ou corriger la précédente) :
        les appels s'exécutent alors un par un, dans l'ordre demandé.
        """
        if all(self._is_read(call) for call in calls):
            return tuple(await asyncio.gather(*(self.execute(call) for call in calls)))
        return tuple([await self.execute(call) for call in calls])

    def _is_read(self, call: ToolCall) -> bool:
        tool = self._tools.get(call.name)
        return tool is not None and tool.effect is ToolEffect.READ

    async def execute(self, call: ToolCall) -> ToolResult:
        """Exécute un appel ; tout échec devient un résultat d'erreur lisible par le LLM."""
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(call.id, f"Outil inconnu : {call.name}", is_error=True)

        try:
            args = tool.parse_args(call.arguments)
        except ValidationError as e:
            return ToolResult(call.id, f"Arguments invalides : {_describe(e)}", is_error=True)

        try:
            return ToolResult(call.id, await tool.run(args))
        except EvaError as e:  # échec attendu (ToolError, service injoignable…) : message lisible
            return ToolResult(call.id, str(e), is_error=True)
        except Exception:
            logger.exception("Échec inattendu de l'outil %s", call.name)
            return ToolResult(call.id, f"Erreur interne de l'outil {call.name}.", is_error=True)


def _describe(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in e['loc']) or 'arguments'} : {e['msg']}"
        for e in error.errors()
    )
