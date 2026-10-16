import asyncio

import pytest

from eva.agent import Toolbox
from eva.domain import EvaError, NoArgs, Tool, ToolEffect, ToolError
from fakes import EchoTool, FailingTool, call


async def test_executes_tool_with_validated_arguments() -> None:
    result = await Toolbox([EchoTool()]).execute(call("echo", value="42"))

    assert (result.content, result.is_error) == ("42", False)


async def test_invalid_arguments_are_reported_to_llm() -> None:
    result = await Toolbox([EchoTool()]).execute(call("echo", value="abc"))

    assert result.is_error
    assert result.content.startswith("Arguments invalides : value")


async def test_unknown_tool_is_reported() -> None:
    result = await Toolbox().execute(call("nope"))

    assert result.is_error
    assert "nope" in result.content


async def test_tool_error_message_is_forwarded() -> None:
    result = await Toolbox([FailingTool(ToolError("Bridge éteint."))]).execute(call("fail"))

    assert (result.content, result.is_error) == ("Bridge éteint.", True)


async def test_any_eva_error_is_forwarded_not_only_tool_error() -> None:
    class ServiceDown(EvaError):
        pass

    toolbox = Toolbox([FailingTool(ServiceDown("Bridge Hue injoignable (ConnectTimeout)"))])

    result = await toolbox.execute(call("fail"))

    assert (result.content, result.is_error) == ("Bridge Hue injoignable (ConnectTimeout)", True)


async def test_unexpected_exception_is_hidden_behind_generic_message() -> None:
    result = await Toolbox([FailingTool(RuntimeError("secret interne"))]).execute(call("fail"))

    assert result.is_error
    assert "secret" not in result.content


async def test_calls_run_in_parallel_and_keep_order() -> None:
    started: list[str] = []
    release = asyncio.Event()

    class Waiter(Tool[NoArgs]):
        effect = ToolEffect.READ
        description = "Attend."
        args_model = NoArgs

        def __init__(self, name: str) -> None:
            self.name = name  # type: ignore[misc]

        async def run(self, args: NoArgs) -> str:
            started.append(self.name)
            if len(started) == 2:
                release.set()
            await asyncio.wait_for(release.wait(), timeout=1)
            return self.name

    results = await Toolbox([Waiter("a"), Waiter("b")]).execute_all([call("a"), call("b")])

    assert [r.content for r in results] == ["a", "b"]


def test_duplicate_tool_names_are_rejected() -> None:
    with pytest.raises(ValueError):
        Toolbox([EchoTool(), EchoTool()])


def test_specs_carry_effect() -> None:
    (spec,) = Toolbox([EchoTool()]).specs()

    assert spec.effect is ToolEffect.READ
