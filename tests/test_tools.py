from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from eva.llm import ToolCall, ToolEffect, ToolSpec
from eva.tools import ClockTool, ToolRegistry
from eva.tools.clock import format_datetime


class FailingTool:
    spec = ToolSpec(
        "fail", "Échoue toujours.", {"type": "object", "properties": {}}, ToolEffect.READ
    )

    def run(self, arguments: dict[str, Any]) -> str:
        raise RuntimeError("boom")


def test_description_is_tagged_with_effect() -> None:
    schema: dict[str, Any] = {"type": "object", "properties": {}}

    read = ToolSpec("r", "Consulte.", schema, ToolEffect.READ)
    action = ToolSpec("a", "Agit.", schema, ToolEffect.ACTION)

    assert read.tagged_description == "[LECTURE SEULE] Consulte."
    assert action.tagged_description.startswith("[ACTION")


def test_unknown_tool_returns_error_result() -> None:
    result = ToolRegistry().execute(ToolCall("c1", "nope", {}))

    assert result.is_error
    assert result.call_id == "c1"


def test_tool_exception_becomes_error_result() -> None:
    result = ToolRegistry([FailingTool()]).execute(ToolCall("c1", "fail", {}))

    assert result.is_error
    assert "boom" in result.content


def test_duplicate_registration_is_rejected() -> None:
    with pytest.raises(ValueError):
        ToolRegistry([FailingTool(), FailingTool()])


def test_format_datetime_in_french_with_weekday() -> None:
    moment = datetime(2026, 10, 17, 0, 23, tzinfo=timezone(timedelta(hours=2)))

    assert format_datetime(moment) == "samedi 17 octobre 2026, 00:23 (UTC+02:00)"


def test_clock_runs() -> None:
    assert ClockTool().run({})
