"""Registre des outils disponibles et exécution des appels."""

import asyncio
import json
import logging
from collections.abc import Iterable, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from eva.domain import EvaError, Tool, ToolCall, ToolEffect, ToolResult, ToolSpec

logger = logging.getLogger(__name__)


class ToolRunner(Protocol):
    """Accès à l'exécution des outils, mis à disposition des plugins."""

    def check(self, call: ToolCall) -> str | None:
        """Problème qui empêcherait l'appel (outil inconnu, arguments invalides), ou `None`."""
        ...

    async def execute(self, call: ToolCall) -> ToolResult: ...


class Toolbox:
    def __init__(
        self,
        tools: Iterable[Tool[Any]] = (),
        *,
        max_calls_per_reply: int = 10,
    ) -> None:
        """`max_calls_per_reply` est un fusible contre l'emballement du LLM, pas une règle
        d'usage : il doit rester bien au-dessus de ce qu'une demande légitime nécessite."""
        self._max_calls = max_calls_per_reply
        self._tools: dict[str, Tool[Any]] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Outil déjà enregistré : {tool.name}")
            self._tools[tool.name] = tool
        # Calculés une fois : un ordre et un contenu stables favorisent le cache du LLM.
        self._specs = [tool.spec() for tool in self._tools.values()]

    def specs(self) -> list[ToolSpec]:
        return list(self._specs)

    def check(self, call: ToolCall) -> str | None:
        """Valide un appel sans l'exécuter."""
        prepared = self._prepare(call)
        return prepared.content if isinstance(prepared, ToolResult) else None

    async def execute_all(self, calls: Sequence[ToolCall]) -> tuple[ToolResult, ...]:
        """Exécute les appels d'une même réponse ; un résultat par appel, dans le même ordre.

        Garde-fous contre un LLM qui s'emballe :
        - un appel identique à un précédent (même outil, mêmes arguments) est ignoré ;
        - au-delà de `max_calls_per_reply` appels distincts, aucun n'est exécuté.

        Des lectures seules s'exécutent en parallèle. Dès qu'une action est présente, l'ordre
        fait partie de l'intention (une action peut compléter ou corriger la précédente) :
        les appels s'exécutent alors un par un, dans l'ordre demandé.
        """
        first_by_signature: dict[str, ToolCall] = {}
        for call in calls:
            first_by_signature.setdefault(_signature(call), call)
        unique = list(first_by_signature.values())

        if len(unique) > self._max_calls:
            refusal = (
                f"Refusé : {len(unique)} appels d'outils distincts dans une seule réponse "
                f"(maximum {self._max_calls}). Aucun n'a été exécuté ; ne demander que les "
                "appels nécessaires, chacun une seule fois."
            )
            return tuple(ToolResult(call.id, refusal, is_error=True) for call in calls)

        result_of = await self._run_unique(unique)
        duplicate = "Doublon ignoré : appel identique déjà exécuté dans cette réponse."
        return tuple(
            result_of[id(call)]
            if first_by_signature[_signature(call)] is call
            else ToolResult(call.id, duplicate, is_error=True)
            for call in calls
        )

    async def _run_unique(self, calls: Sequence[ToolCall]) -> dict[int, ToolResult]:
        """Résultat de chaque appel (sans doublon), indexé par l'identité de l'appel."""
        if any(self._is_action(call) for call in calls):
            results = [await self.execute(call) for call in calls]
        else:
            results = list(await asyncio.gather(*(self.execute(call) for call in calls)))
        return {id(call): result for call, result in zip(calls, results, strict=True)}

    async def execute(self, call: ToolCall) -> ToolResult:
        """Exécute un appel ; tout échec devient un résultat d'erreur lisible par le LLM."""
        prepared = self._prepare(call)
        if isinstance(prepared, ToolResult):
            return prepared
        tool, args = prepared

        try:
            return ToolResult(call.id, await tool.run(args))
        except EvaError as e:  # échec attendu (ToolError, service injoignable…) : message lisible
            return ToolResult(call.id, str(e), is_error=True)
        except Exception:
            logger.exception("Échec inattendu de l'outil %s", call.name)
            return ToolResult(call.id, f"Erreur interne de l'outil {call.name}.", is_error=True)

    def _prepare(self, call: ToolCall) -> tuple[Tool[Any], BaseModel] | ToolResult:
        """Outil et arguments validés, ou résultat d'erreur expliquant pourquoi c'est impossible."""
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(call.id, f"Outil inconnu : {call.name}", is_error=True)
        try:
            return tool, tool.parse_args(call.arguments)
        except ValidationError as e:
            return ToolResult(call.id, f"Arguments invalides : {_describe(e)}", is_error=True)

    def _is_action(self, call: ToolCall) -> bool:
        tool = self._tools.get(call.name)
        return tool is not None and tool.effect is ToolEffect.ACTION


class DeferredToolRunner:
    """`ToolRunner` branché après coup sur la `Toolbox`.

    Les plugins reçoivent cet accès pendant leur préparation, avant que la `Toolbox`
    réunissant les outils de tous les plugins n'existe.
    """

    def __init__(self) -> None:
        self._toolbox: Toolbox | None = None

    def bind(self, toolbox: Toolbox) -> None:
        self._toolbox = toolbox

    def check(self, call: ToolCall) -> str | None:
        return self._bound().check(call)

    async def execute(self, call: ToolCall) -> ToolResult:
        return await self._bound().execute(call)

    def _bound(self) -> Toolbox:
        if self._toolbox is None:
            raise EvaError("Les outils ne sont pas encore disponibles.")
        return self._toolbox


def _signature(call: ToolCall) -> str:
    """Identité d'un appel : outil et arguments, indépendamment de son identifiant."""
    return f"{call.name}:{json.dumps(call.arguments, sort_keys=True, default=str)}"


def _describe(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in e['loc']) or 'arguments'} : {e['msg']}"
        for e in error.errors()
    )
