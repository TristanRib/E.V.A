from eva.agent import Conversation
from eva.domain import AssistantMessage, ToolCall, ToolResult, ToolResultsMessage, UserMessage


def test_rollback_restores_checkpoint() -> None:
    conversation = Conversation()
    conversation.append(UserMessage("un"))
    checkpoint = conversation.checkpoint()
    conversation.append(UserMessage("deux"))

    conversation.rollback(checkpoint)

    assert conversation.messages == (UserMessage("un"),)


def test_trim_keeps_last_turns_without_splitting_tool_calls() -> None:
    conversation = Conversation(max_turns=2)
    for message in (
        UserMessage("un"),
        AssistantMessage("1"),
        UserMessage("deux"),
        AssistantMessage("", tool_calls=(ToolCall("c", "echo", {}),)),
        ToolResultsMessage((ToolResult("c", "ok"),)),
        AssistantMessage("2"),
        UserMessage("trois"),
        AssistantMessage("3"),
    ):
        conversation.append(message)

    conversation.trim()

    messages = conversation.messages
    assert messages[0] == UserMessage("deux")
    assert isinstance(messages[2], ToolResultsMessage)
    assert messages[-1] == AssistantMessage("3")
