"""Noyau d'E.V.A : concepts partagés par toutes les couches.

Ce paquet ne dépend d'aucun autre module d'E.V.A ; tous les autres dépendent de lui.
"""

from eva.domain.errors import ConfigurationError, EvaError, ToolError
from eva.domain.messages import (
    AssistantMessage,
    Message,
    ToolCall,
    ToolResult,
    ToolResultsMessage,
    UserMessage,
)
from eva.domain.text import normalize
from eva.domain.tools import NoArgs, Tool, ToolEffect, ToolSpec, choice, with_choices

__all__ = [
    "AssistantMessage",
    "ConfigurationError",
    "EvaError",
    "Message",
    "NoArgs",
    "Tool",
    "ToolCall",
    "ToolEffect",
    "ToolError",
    "ToolResult",
    "ToolResultsMessage",
    "ToolSpec",
    "UserMessage",
    "choice",
    "normalize",
    "with_choices",
]
