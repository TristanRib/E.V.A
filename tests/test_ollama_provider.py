"""Fournisseur Ollama, testé sans serveur grâce à un faux client."""

from collections.abc import Iterator
from typing import Any

import ollama

from eva.llm import (
    AssistantMessage,
    Message,
    StopReason,
    ToolCall,
    ToolResult,
    ToolResultsMessage,
    UserMessage,
)
from eva.llm.ollama import OllamaProvider, _to_api_messages


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


def provider_streaming(*chunks: ollama.ChatResponse) -> OllamaProvider:
    provider = OllamaProvider()

    def fake_chat(**kwargs: Any) -> Iterator[ollama.ChatResponse]:
        assert kwargs["stream"] is True
        return iter(chunks)

    provider._client.chat = fake_chat  # type: ignore[assignment,method-assign]
    return provider


def complete(provider: OllamaProvider, on_text: list[str] | None = None) -> Any:
    return provider.complete(
        system="system",
        messages=[UserMessage("Salut")],
        tools=[],
        on_text=on_text.append if on_text is not None else None,
    )


def test_streamed_chunks_are_forwarded_and_assembled() -> None:
    provider = provider_streaming(chunk("Bon"), chunk("jour"), chunk(done_reason="stop"))
    received: list[str] = []

    completion = complete(provider, received)

    assert received == ["Bon", "jour"]
    assert completion.message.text == "Bonjour"
    assert completion.stop_reason is StopReason.END_TURN


def test_length_limit_is_reported_as_max_tokens() -> None:
    provider = provider_streaming(chunk("Il était"), chunk(done_reason="length"))

    assert complete(provider).stop_reason is StopReason.MAX_TOKENS


def test_tool_calls_get_unique_ids() -> None:
    call = ollama.Message.ToolCall(
        function=ollama.Message.ToolCall.Function(name="echo", arguments={"value": 1})
    )
    provider = provider_streaming(chunk(tool_calls=[call, call]), chunk(done_reason="stop"))

    completion = complete(provider)

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
