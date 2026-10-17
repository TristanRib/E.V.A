"""Lancement des routines : vérification complète, puis exécution des étapes dans l'ordre.

`StepRunner` est le contrat attendu pour exécuter une étape ; il est fourni par E.V.A.
"""

from collections.abc import Collection, Sequence
from typing import Protocol

from eva.domain import ToolCall, ToolResult, normalize
from eva.plugins.routines.domain import Routine, RoutineError


class StepRunner(Protocol):
    def check(self, call: ToolCall) -> str | None: ...

    async def execute(self, call: ToolCall) -> ToolResult: ...


class RoutineRunner:
    def __init__(
        self,
        routines: Sequence[Routine],
        runner: StepRunner,
        *,
        forbidden_tools: Collection[str] = (),
    ) -> None:
        """`forbidden_tools` : outils qu'une étape ne peut pas appeler (ex. le lancement
        d'une routine lui-même, qui provoquerait une boucle)."""
        self._routines = {normalize(r.name): r for r in routines}
        self._runner = runner
        self._forbidden = frozenset(forbidden_tools)

    def get(self, name: str) -> Routine:
        routine = self._routines.get(normalize(name))
        if routine is None:
            raise RoutineError(f"Routine inconnue : {name}. Routines : {', '.join(self.names)}.")
        return routine

    @property
    def names(self) -> list[str]:
        return [routine.name for routine in self._routines.values()]

    async def run(self, name: str) -> tuple[Routine, list[ToolResult]]:
        """Vérifie toutes les étapes avant d'en exécuter une seule, puis les déroule.

        Raises:
            RoutineError: routine inconnue ou mal configurée (rien n'est modifié), ou étape
                en échec (les étapes précédentes restent appliquées).
        """
        routine = self.get(name)
        calls = [
            ToolCall(id=f"routine-{i}", name=step.tool, arguments=step.arguments)
            for i, step in enumerate(routine.steps, start=1)
        ]

        problems = [
            f"étape {i} ({call.name}) : {problem}"
            for i, call in enumerate(calls, start=1)
            if (problem := self._check(call))
        ]
        if problems:
            raise RoutineError(
                f"La routine « {routine.name} » est mal configurée, rien n'a été modifié. "
                + " ; ".join(problems)
            )

        results: list[ToolResult] = []
        for i, call in enumerate(calls, start=1):
            result = await self._runner.execute(call)
            if result.is_error:
                raise RoutineError(
                    f"Routine « {routine.name} » interrompue à l'étape {i}/{len(calls)} "
                    f"({call.name}) : {result.content}"
                )
            results.append(result)
        return routine, results

    def _check(self, call: ToolCall) -> str | None:
        if call.name in self._forbidden:
            return "outil interdit dans une routine"
        return self._runner.check(call)
