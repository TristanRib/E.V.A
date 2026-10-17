import asyncio

import pytest

from eva.application import DeferredToolRunner, Toolbox
from eva.domain import EvaError, NoArgs, Tool, ToolCall, ToolEffect, ToolError
from fakes import EchoArgs, EchoTool, FailingTool, call


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
            self.name = name

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
            self.name = name
            self._delay = delay

        async def run(self, args: NoArgs) -> str:
            await asyncio.sleep(self._delay)
            applied.append(self.name)
            return self.name

    toolbox = Toolbox([Switch("first", 0.05), Switch("second", 0)])

    await toolbox.execute_all([call("first"), call("second")])

    assert applied == ["first", "second"]


async def test_identical_calls_in_one_reply_run_once() -> None:
    applied: list[int] = []

    class Counter(Tool[EchoArgs]):
        name = "count"
        description = "Compte."
        effect = ToolEffect.ACTION
        args_model = EchoArgs

        async def run(self, args: EchoArgs) -> str:
            applied.append(args.value)
            return "ok"

    calls = [ToolCall(f"c{i}", "count", {"value": v}) for i, v in enumerate([1, 1, 2, 1])]

    results = await Toolbox([Counter()]).execute_all(calls)

    assert applied == [1, 2]
    assert [r.call_id for r in results] == ["c0", "c1", "c2", "c3"]
    assert [r.is_error for r in results] == [False, True, False, True]
    assert "Doublon" in results[1].content


async def test_too_many_distinct_calls_execute_nothing() -> None:
    applied: list[int] = []

    class Counter(Tool[EchoArgs]):
        name = "count"
        description = "Compte."
        effect = ToolEffect.ACTION
        args_model = EchoArgs

        async def run(self, args: EchoArgs) -> str:
            applied.append(args.value)
            return "ok"

    calls = [ToolCall(f"c{i}", "count", {"value": i}) for i in range(4)]

    results = await Toolbox([Counter()], max_calls_per_reply=3).execute_all(calls)

    assert applied == []
    assert len(results) == 4
    assert all(r.is_error and "Aucun n'a été exécuté" in r.content for r in results)


def test_check_validates_without_executing() -> None:
    toolbox = Toolbox([EchoTool()])

    assert toolbox.check(call("echo", value=1)) is None
    assert toolbox.check(call("echo", value="abc")) == "Arguments invalides : value : " + (
        "Input should be a valid integer, unable to parse string as an integer"
    )
    assert toolbox.check(call("nope")) == "Outil inconnu : nope"


async def test_deferred_runner_works_once_bound() -> None:
    runner = DeferredToolRunner()

    with pytest.raises(EvaError):
        runner.check(call("echo", value=1))

    runner.bind(Toolbox([EchoTool()]))

    assert runner.check(call("echo", value=1)) is None
    assert (await runner.execute(call("echo", value=1))).content == "1"


def test_duplicate_tool_names_are_rejected() -> None:
    with pytest.raises(ValueError):
        Toolbox([EchoTool(), EchoTool()])


def test_specs_carry_effect() -> None:
    (spec,) = Toolbox([EchoTool()]).specs()

    assert spec.effect is ToolEffect.READ
