"""Contrat d'un outil et registre qui les expose au LLM."""

import logging
from collections.abc import Iterable
from typing import Any, Protocol

from eva.llm import ToolCall, ToolResult, ToolSpec

logger = logging.getLogger(__name__)


class Tool(Protocol):
    """Une capacité d'E.V.A que le LLM peut déclencher."""

    @property
    def spec(self) -> ToolSpec: ...

    def run(self, arguments: dict[str, Any]) -> str:
        """Exécute l'outil et renvoie un résultat textuel destiné au LLM.

        Toute exception est rapportée au LLM comme une erreur d'outil.
        """
        ...


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        name = tool.spec.name
        if name in self._tools:
            raise ValueError(f"Outil déjà enregistré : {name}")
        self._tools[name] = tool

    def specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    def execute(self, call: ToolCall) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(call.id, f"Outil inconnu : {call.name}", is_error=True)
        try:
            return ToolResult(call.id, tool.run(call.arguments))
        except Exception as e:
            logger.exception("Échec de l'outil %s", call.name)
            return ToolResult(call.id, f"{type(e).__name__}: {e}", is_error=True)
