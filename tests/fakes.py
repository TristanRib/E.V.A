"""Doublures de test partagées : faux LLM, outils et plugins factices, collecteur d'événements."""

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from eva.application import AgentEvent, Completion, StopReason, TextCallback
from eva.domain import AssistantMessage, Message, NoArgs, Tool, ToolCall, ToolEffect, ToolSpec
from eva.plugins import NoConfig, Plugin, PluginContext, PluginUnavailable


class ScriptedLLM:
    """Faux fournisseur qui rejoue des réponses (ou exceptions) prédéfinies."""

    name = "scripted"

    def __init__(self, *script: Completion | BaseException) -> None:
        self._script = list(script)
        self.calls: list[tuple[Message, ...]] = []

    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        on_text: TextCallback | None = None,
    ) -> Completion:
        self.calls.append(tuple(messages))
        step = self._script.pop(0)
        if isinstance(step, BaseException):
            raise step
        if on_text and step.message.text:
            on_text(step.message.text)
        return step

    async def aclose(self) -> None:
        pass


def reply(text: str) -> Completion:
    return Completion(AssistantMessage(text), StopReason.END_TURN)


def tool_request(*calls: ToolCall) -> Completion:
    return Completion(AssistantMessage("", tool_calls=calls), StopReason.TOOL_USE)


class EchoArgs(BaseModel):
    value: int


class EchoTool(Tool[EchoArgs]):
    name = "echo"
    description = "Renvoie son argument."
    effect = ToolEffect.READ
    args_model = EchoArgs

    async def run(self, args: EchoArgs) -> str:
        return str(args.value)


class FailingTool(Tool[NoArgs]):
    name = "fail"
    description = "Échoue toujours."
    effect = ToolEffect.ACTION
    args_model = NoArgs

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def run(self, args: NoArgs) -> str:
        raise self._error


class EventRecorder:
    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    def emit(self, event: AgentEvent) -> None:
        self.events.append(event)

    def of_type[T](self, kind: type[T]) -> list[T]:
        return [e for e in self.events if isinstance(e, kind)]


def call(name: str, **arguments: Any) -> ToolCall:
    return ToolCall(id=f"id-{name}", name=name, arguments=arguments)


class EchoPlugin(Plugin[NoConfig]):
    config_model = NoConfig

    async def setup(self, context: PluginContext[NoConfig]) -> Sequence[Tool[Any]]:
        return [EchoTool()]


class UnavailablePlugin(Plugin[NoConfig]):
    config_model = NoConfig

    async def setup(self, context: PluginContext[NoConfig]) -> Sequence[Tool[Any]]:
        raise PluginUnavailable("non configuré")


class CrashingPlugin(Plugin[NoConfig]):
    config_model = NoConfig

    async def setup(self, context: PluginContext[NoConfig]) -> Sequence[Tool[Any]]:
        raise RuntimeError("boom")


class ValueConfig(BaseModel):
    value: int


class ConfiguredPlugin(Plugin[ValueConfig]):
    """Expose un outil dont le nom reflète la configuration reçue."""

    config_model = ValueConfig

    async def setup(self, context: PluginContext[ValueConfig]) -> Sequence[Tool[Any]]:
        tool = EchoTool()
        tool.name = f"echo_{context.config.value}"  # type: ignore[misc]
        return [tool]
