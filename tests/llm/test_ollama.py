"""Fournisseur Ollama, testé sans serveur grâce à un faux client asynchrone."""

from collections.abc import AsyncIterator
from typing import Any

import ollama

from eva.domain import (
    AssistantMessage,
    Message,
    ToolCall,
    ToolEffect,
    ToolResult,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)
from eva.llm import Completion, StopReason, describe_tool
from eva.llm.providers.ollama import OllamaProvider, OllamaSettings, _to_api_messages


def chunk(
    content: str = "",
    tool_calls: list[ollama.Message.ToolCall] | None = None,
    done_reason: str | None = None,
) -> ollama.ChatResponse:
    return ollama.ChatResponse(
        model="test",
        message=ollama.Message(role="assistant", content=content, tool_calls=tool_calls),
        done=done_reason is not None,
        done_reason=done_reason,
    )


class FakeChat:
    def __init__(self, *chunks: ollama.ChatResponse) -> None:
        self._chunks = chunks
        self.kwargs: dict[str, Any] = {}

    async def __call__(self, **kwargs: Any) -> AsyncIterator[ollama.ChatResponse]:
        self.kwargs = kwargs

        async def stream() -> AsyncIterator[ollama.ChatResponse]:
            for c in self._chunks:
                yield c

        return stream()


async def complete(
    *chunks: ollama.ChatResponse, on_text: list[str] | None = None
) -> tuple[Completion, FakeChat]:
    provider = OllamaProvider(OllamaSettings(context_size=4096, keep_alive="5m"))
    fake = FakeChat(*chunks)
    provider._client.chat = fake  # type: ignore[method-assign,assignment]
    completion = await provider.complete(
        system="system",
        messages=[UserMessage("Salut")],
        tools=[],
        on_text=on_text.append if on_text is not None else None,
    )
    return completion, fake


async def test_streamed_chunks_are_forwarded_and_assembled() -> None:
    received: list[str] = []

    completion, fake = await complete(
        chunk("Bon"), chunk("jour"), chunk(done_reason="stop"), on_text=received
    )

    assert received == ["Bon", "jour"]
    assert completion.message.text == "Bonjour"
    assert completion.stop_reason is StopReason.END_TURN
    assert fake.kwargs["stream"] is True
    assert fake.kwargs["options"]["num_ctx"] == 4096
    assert fake.kwargs["keep_alive"] == "5m"


async def test_length_limit_is_reported_as_max_tokens() -> None:
    completion, _ = await complete(chunk("Il était"), chunk(done_reason="length"))

    assert completion.stop_reason is StopReason.MAX_TOKENS


async def test_tool_calls_get_unique_ids() -> None:
    api_call = ollama.Message.ToolCall(
        function=ollama.Message.ToolCall.Function(name="echo", arguments={"value": 1})
    )

    completion, _ = await complete(
        chunk(tool_calls=[api_call, api_call]), chunk(done_reason="stop")
    )

    assert completion.stop_reason is StopReason.TOOL_USE
    first, second = completion.message.tool_calls
    assert (first.name, first.arguments) == ("echo", {"value": 1})
    assert first.id != second.id


def test_tool_result_is_sent_with_tool_name() -> None:
    history: list[Message] = [
        UserMessage("Écho ?"),
        AssistantMessage("", tool_calls=(ToolCall("c1", "echo", {"value": 1}),)),
        ToolResultsMessage((ToolResult("c1", "1"), ToolResult("c1", "boom", is_error=True))),
    ]

    user, assistant, ok, failed = _to_api_messages(history)

    assert (user.role, user.content) == ("user", "Écho ?")
    assert assistant.tool_calls is not None
    assert assistant.tool_calls[0].function.name == "echo"
    assert (ok.role, ok.tool_name, ok.content) == ("tool", "echo", "1")
    assert failed.content == "Erreur : boom"


def test_tool_description_is_tagged_with_effect() -> None:
    schema: dict[str, Any] = {"type": "object", "properties": {}}

    read = describe_tool(ToolSpec("r", "Consulte.", schema, ToolEffect.READ))
    action = describe_tool(ToolSpec("a", "Agit.", schema, ToolEffect.ACTION))

    assert read == "[LECTURE SEULE] Consulte."
    assert action.startswith("[ACTION")
