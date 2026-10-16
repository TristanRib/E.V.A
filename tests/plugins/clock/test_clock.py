from datetime import datetime, timedelta, timezone

from eva.domain import NoArgs
from eva.plugins.clock.tools import ClockTool, format_datetime


def test_format_datetime_in_french_with_weekday() -> None:
    moment = datetime(2026, 10, 17, 0, 23, tzinfo=timezone(timedelta(hours=2)))

    assert format_datetime(moment) == "samedi 17 octobre 2026, 00:23 (UTC+02:00)"


async def test_clock_tool_runs() -> None:
    assert await ClockTool().run(NoArgs())
