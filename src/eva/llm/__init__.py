"""Abstraction des fournisseurs de LLM.

Le reste d'E.V.A ne dépend que de ce module : `LLMProvider` et les types neutres.
"""

from eva.llm.base import LLMError, LLMProvider, TextCallback
from eva.llm.factory import create_provider
from eva.llm.types import (
    AssistantMessage,
    Completion,
    Message,
    StopReason,
    ToolCall,
    ToolResult,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)

__all__ = [
    "AssistantMessage",
    "Completion",
    "LLMError",
    "LLMProvider",
    "Message",
    "StopReason",
    "TextCallback",
    "ToolCall",
    "ToolResult",
    "ToolResultsMessage",
    "ToolSpec",
    "UserMessage",
    "create_provider",
]
