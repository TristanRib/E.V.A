"""Abstraction des fournisseurs de LLM.

L'agent ne dépend que de ce module : `LLMProvider` et ses types.
"""

from eva.llm.factory import create_provider
from eva.llm.provider import (
    Completion,
    LLMError,
    LLMProvider,
    StopReason,
    TextCallback,
    describe_tool,
)

__all__ = [
    "Completion",
    "LLMError",
    "LLMProvider",
    "StopReason",
    "TextCallback",
    "create_provider",
    "describe_tool",
]
