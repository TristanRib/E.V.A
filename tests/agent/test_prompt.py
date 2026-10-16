from eva.agent import build_system_prompt


def test_prompt_uses_user_name_and_stays_generic() -> None:
    prompt = build_system_prompt("Alice")

    assert "assistante personnelle de Alice" in prompt
    assert "[ACTION]" in prompt
    assert "hue" not in prompt.lower()
