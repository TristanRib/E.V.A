"""Couche application : l'agent conversationnel et les contrats dont il dépend.

`LLMProvider` est défini ici (le « port ») ; ses implémentations vivent dans
`eva.infrastructure.llm`.
"""

from eva.application.agent import Agent, AgentError
from eva.application.conversation import Conversation
from eva.application.events import (
    AgentEvent,
    EventSink,
    LoggingSink,
    TextDelta,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
)
from eva.application.llm import (
    Completion,
    LLMError,
    LLMProvider,
    StopReason,
    TextCallback,
    describe_tool,
)
from eva.application.prompt import build_system_prompt
from eva.application.toolbox import DeferredToolRunner, Toolbox, ToolRunner

__all__ = [
    "Agent",
    "AgentError",
    "AgentEvent",
    "Completion",
    "Conversation",
    "DeferredToolRunner",
    "EventSink",
    "LLMError",
    "LLMProvider",
    "LoggingSink",
    "StopReason",
    "TextCallback",
    "TextDelta",
    "ToolCallFinished",
    "ToolCallStarted",
    "ToolRunner",
    "Toolbox",
    "TurnFinished",
    "build_system_prompt",
    "describe_tool",
]
