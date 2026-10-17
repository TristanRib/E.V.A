import asyncio

import pytest

from eva.application import (
    Agent,
    AgentError,
    Completion,
    Conversation,
    LLMError,
    StopReason,
    TextDelta,
    Toolbox,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
)
from eva.application.agent import TRUNCATED_NOTE
from eva.domain import AssistantMessage, ToolResultsMessage, UserMessage
from fakes import EchoTool, EventRecorder, ScriptedLLM, call, reply, tool_request


def make_agent(llm: ScriptedLLM, *, max_steps: int = 10) -> Agent:
    return Agent(llm, Toolbox([EchoTool()]), "system", Conversation(), max_steps=max_steps)


async def test_simple_reply_is_recorded() -> None:
    agent = make_agent(ScriptedLLM(reply("Bonjour !")))

    assert await agent.ask("Salut") == "Bonjour !"
    assert agent.conversation.messages == (UserMessage("Salut"), AssistantMessage("Bonjour !"))


async def test_tool_result_is_sent_back_and_events_emitted() -> None:
    llm = ScriptedLLM(tool_request(call("echo", value=42)), reply("C'est 42."))
    events = EventRecorder()

    await make_agent(llm).ask("Écho", sink=events)

    last_sent = llm.calls[1][-1]
    assert isinstance(last_sent, ToolResultsMessage)
    assert last_sent.results[0].content == "42"
    assert [type(e) for e in events.events] == [
        ToolCallStarted,
        ToolCallFinished,
        TextDelta,
        TurnFinished,
    ]
    assert events.of_type(TurnFinished) == [TurnFinished("C'est 42.")]


async def test_observers_receive_events_too() -> None:
    observer = EventRecorder()
    agent = Agent(
        ScriptedLLM(reply("Ok")), Toolbox(), "system", Conversation(), observers=[observer]
    )

    await agent.ask("Salut")

    assert observer.of_type(TurnFinished) == [TurnFinished("Ok")]


async def test_llm_error_rolls_back_the_turn() -> None:
    agent = make_agent(ScriptedLLM(reply("Un"), LLMError("panne")))
    await agent.ask("Premier")

    with pytest.raises(LLMError):
        await agent.ask("Second")

    assert len(agent.conversation.messages) == 2


async def test_cancellation_mid_turn_rolls_back_the_turn() -> None:
    gate = asyncio.Event()

    class SlowLLM(ScriptedLLM):
        async def complete(self, **kwargs: object) -> Completion:
            await gate.wait()
            raise AssertionError("ne doit pas être atteint")

    agent = Agent(SlowLLM(), Toolbox(), "system", Conversation())
    task = asyncio.create_task(agent.ask("Long"))
    await asyncio.sleep(0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert agent.conversation.messages == ()


async def test_truncated_reply_is_flagged() -> None:
    truncated = Completion(AssistantMessage("Il était une"), StopReason.MAX_TOKENS)
    events = EventRecorder()

    reply_text = await make_agent(ScriptedLLM(truncated)).ask("Histoire", sink=events)

    assert reply_text == "Il était une" + TRUNCATED_NOTE
    assert "".join(e.text for e in events.of_type(TextDelta)) == reply_text


async def test_gives_up_after_max_steps() -> None:
    echo = tool_request(call("echo", value=1))
    agent = make_agent(ScriptedLLM(echo, echo), max_steps=2)

    with pytest.raises(AgentError):
        await agent.ask("Boucle")
    assert agent.conversation.messages == ()


async def test_conversation_is_trimmed_after_each_turn() -> None:
    agent = Agent(
        ScriptedLLM(reply("1"), reply("2"), reply("3")),
        Toolbox(),
        "system",
        Conversation(max_turns=2),
    )
    for text in ("un", "deux", "trois"):
        await agent.ask(text)

    assert agent.conversation.messages[0] == UserMessage("deux")
