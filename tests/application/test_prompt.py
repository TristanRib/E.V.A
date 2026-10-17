from eva.application import build_system_prompt
from eva.plugins import PLUGINS


def test_prompt_uses_user_name() -> None:
    assert "assistante personnelle de Alice" in build_system_prompt("Alice")


def test_prompt_states_generic_action_rule() -> None:
    assert "[ACTION]" in build_system_prompt("Alice")


def test_prompt_mentions_no_plugin() -> None:
    prompt = build_system_prompt("Alice").lower()

    assert not [name for name in PLUGINS if name in prompt]
