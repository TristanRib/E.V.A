from pathlib import Path

from eva.tools.hue.pairing import update_env_file


def test_update_env_file_replaces_and_appends(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("# commentaire\nHUE_BRIDGE_IP=\nEVA_MODEL=x\n", encoding="utf-8")

    update_env_file(env, {"HUE_BRIDGE_IP": "192.168.1.10", "HUE_APP_KEY": "abc"})

    assert env.read_text(encoding="utf-8") == (
        "# commentaire\nHUE_BRIDGE_IP=192.168.1.10\nEVA_MODEL=x\nHUE_APP_KEY=abc\n"
    )


def test_update_env_file_creates_missing_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"

    update_env_file(env, {"HUE_APP_KEY": "abc"})

    assert env.read_text(encoding="utf-8") == "HUE_APP_KEY=abc\n"
