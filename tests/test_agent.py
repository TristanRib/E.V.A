from collections.abc import Sequence
from typing import Any

import pytest

from eva.core import Agent, AgentError
from eva.core.agent import TRUNCATED_NOTE
from eva.llm import (
    AssistantMessage,
    Completion,
    LLMError,
    Message,
    StopReason,
    TextCallback,
    ToolCall,
    ToolEffect,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)
from eva.tools import ToolRegistry


class ScriptedLLM:
    """Faux fournisseur qui rejoue des réponses prédéfinies."""

    name = "scripted"

    def __init__(self, *completions: Completion | BaseException) -> None:
        self._script = list(completions)
        self.calls: list[tuple[Message, ...]] = []

    def complete(
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


class EchoTool:
    spec = ToolSpec(
        "echo", "Renvoie son argument.", {"type": "object", "properties": {}}, ToolEffect.READ
    )

    def run(self, arguments: dict[str, Any]) -> str:
        return str(arguments["value"])


def reply(text: str) -> Completion:
    return Completion(AssistantMessage(text), StopReason.END_TURN)


def tool_request(*calls: ToolCall) -> Completion:
    return Completion(AssistantMessage("", tool_calls=calls), StopReason.TOOL_USE)


def make_agent(llm: ScriptedLLM, *, max_steps: int = 10) -> Agent:
    return Agent(llm, ToolRegistry([EchoTool()]), "system", max_steps=max_steps)


def test_simple_reply_is_recorded_in_history() -> None:
    agent = make_agent(ScriptedLLM(reply("Bonjour !")))

    assert agent.ask("Salut") == "Bonjour !"
    assert agent.history == (UserMessage("Salut"), AssistantMessage("Bonjour !"))


def test_tool_call_result_is_sent_back_to_llm() -> None:
    llm = ScriptedLLM(
        tool_request(ToolCall("c1", "echo", {"value": 42})),
        reply("C'est 42."),
    )
    agent = make_agent(llm)

    assert agent.ask("Fais écho") == "C'est 42."
    second_call = llm.calls[1]
    assert isinstance(second_call[-1], ToolResultsMessage)
    assert second_call[-1].results[0].content == "42"
    assert not second_call[-1].results[0].is_error


def test_llm_error_rolls_back_the_turn() -> None:
    agent = make_agent(ScriptedLLM(reply("Un"), LLMError("panne")))
    agent.ask("Premier")

    with pytest.raises(LLMError):
        agent.ask("Second")

    assert len(agent.history) == 2


def test_interrupt_mid_turn_rolls_back_the_turn() -> None:
    llm = ScriptedLLM(
        reply("Un"),
        tool_request(ToolCall("c1", "echo", {"value": 1})),
        KeyboardInterrupt(),
    )
    agent = make_agent(llm)
    agent.ask("Premier")

    with pytest.raises(KeyboardInterrupt):
        agent.ask("Second")

    assert len(agent.history) == 2


def test_streamed_text_reaches_callback() -> None:
    llm = ScriptedLLM(tool_request(ToolCall("c1", "echo", {"value": 1})), reply("Fini."))
    chunks: list[str] = []

    make_agent(llm).ask("Go", on_text=chunks.append)

    assert "".join(chunks) == "Fini."


def test_truncated_reply_is_flagged() -> None:
    truncated = Completion(AssistantMessage("Il était une"), StopReason.MAX_TOKENS)
    chunks: list[str] = []

    reply_text = make_agent(ScriptedLLM(truncated)).ask("Histoire", on_text=chunks.append)

    assert reply_text == "Il était une" + TRUNCATED_NOTE
    assert "".join(chunks) == reply_text


def test_history_keeps_only_last_turns_without_splitting_tool_calls() -> None:
    llm = ScriptedLLM(
        reply("1"),
        tool_request(ToolCall("c1", "echo", {"value": 2})),
        reply("2"),
        reply("3"),
    )
    agent = Agent(llm, ToolRegistry([EchoTool()]), "system", max_turns=2)

    for text in ("un", "deux", "trois"):
        agent.ask(text)

    history = agent.history
    assert history[0] == UserMessage("deux")
    assert isinstance(history[2], ToolResultsMessage)
    assert history[-1] == AssistantMessage("3")


def test_gives_up_after_max_steps() -> None:
    call = ToolCall("c", "echo", {"value": 1})
    agent = make_agent(ScriptedLLM(tool_request(call), tool_request(call)), max_steps=2)

    with pytest.raises(AgentError):
        agent.ask("Boucle")
    assert agent.history == ()
