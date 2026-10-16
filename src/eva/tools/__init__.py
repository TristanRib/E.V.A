"""Outils exposés au LLM via le function calling."""

from eva.tools.base import Tool, ToolRegistry
from eva.tools.clock import ClockTool


def default_tools() -> ToolRegistry:
    """Registre des outils activés par défaut."""
    return ToolRegistry([ClockTool()])


__all__ = ["ClockTool", "Tool", "ToolRegistry", "default_tools"]
