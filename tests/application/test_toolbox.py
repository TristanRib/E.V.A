import asyncio

import pytest

from eva.application import Toolbox
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
    result = await Toolbox([FailingTool(ToolError("Opération refusée."))]).execute(call("fail"))

    assert (result.content, result.is_error) == ("Opération refusée.", True)


async def test_any_eva_error_is_forwarded_not_only_tool_error() -> None:
    class ServiceDown(EvaError):
        pass

    toolbox = Toolbox([FailingTool(ServiceDown("Service injoignable."))])

    result = await toolbox.execute(call("fail"))

    assert (result.content, result.is_error) == ("Service injoignable.", True)


async def test_unexpected_exception_is_hidden_behind_generic_message() -> None:
    result = await Toolbox([FailingTool(RuntimeError("secret interne"))]).execute(call("fail"))

    assert result.is_error
    assert "secret" not in result.content


async def test_reads_run_in_parallel_and_keep_order() -> None:
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
            if len(started) == 2:  # ne se débloque que si les deux tournent en même temps
                release.set()
            await asyncio.wait_for(release.wait(), timeout=1)
            return self.name

    results = await Toolbox([Waiter("a"), Waiter("b")]).execute_all([call("a"), call("b")])

    assert [r.content for r in results] == ["a", "b"]


async def test_actions_run_one_by_one_in_requested_order() -> None:
    """La première action, plus lente, doit quand même s'appliquer avant la seconde."""
    applied: list[str] = []

    class Switch(Tool[NoArgs]):
        effect = ToolEffect.ACTION
        description = "Agit."
        args_model = NoArgs

        def __init__(self, name: str, delay: float) -> None:
            self.name = name  # type: ignore[misc]
            self._delay = delay

        async def run(self, args: NoArgs) -> str:
            await asyncio.sleep(self._delay)
            applied.append(self.name)
            return self.name

    toolbox = Toolbox([Switch("first", 0.05), Switch("second", 0)])

    await toolbox.execute_all([call("first"), call("second")])

    assert applied == ["first", "second"]


def test_duplicate_tool_names_are_rejected() -> None:
    with pytest.raises(ValueError):
        Toolbox([EchoTool(), EchoTool()])


def test_specs_carry_effect() -> None:
    (spec,) = Toolbox([EchoTool()]).specs()

    assert spec.effect is ToolEffect.READ
