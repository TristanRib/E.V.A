"""Appairage : écriture d'`eva.toml` et de `.env`."""

from pathlib import Path

from eva.plugins.hue.cli import configured_bridge_ips, save_home, update_env_file

EXISTING = """\
# Ma configuration
user_name = "Tristan"  # prénom

[[plugins.hue.homes]]
name = "Maison"
bridge_ip = "192.168.1.10"
"""


def test_save_home_appends_and_preserves_comments(tmp_path: Path) -> None:
    config = tmp_path / "eva.toml"
    config.write_text(EXISTING, encoding="utf-8")

    save_home(config, "Chalet", "10.0.0.5")

    text = config.read_text(encoding="utf-8")
    assert text.startswith('# Ma configuration\nuser_name = "Tristan"  # prénom\n')
    assert configured_bridge_ips(config) == {"192.168.1.10", "10.0.0.5"}


def test_save_home_updates_existing_home(tmp_path: Path) -> None:
    config = tmp_path / "eva.toml"
    config.write_text(EXISTING, encoding="utf-8")

    save_home(config, "maison", "192.168.1.20")

    assert configured_bridge_ips(config) == {"192.168.1.20"}


def test_save_home_creates_missing_file(tmp_path: Path) -> None:
    config = tmp_path / "eva.toml"

    save_home(config, "Maison", "192.168.1.10")

    assert config.read_text(encoding="utf-8") == (
        '[[plugins.hue.homes]]\nname = "Maison"\nbridge_ip = "192.168.1.10"\n'
    )


def test_update_env_file_replaces_and_appends(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("# commentaire\nHUE_KEY_MAISON=ancienne\nAUTRE=x\n", encoding="utf-8")

    update_env_file(env, {"HUE_KEY_MAISON": "nouvelle", "HUE_KEY_CHALET": "abc"})

    assert env.read_text(encoding="utf-8") == (
        "# commentaire\nHUE_KEY_MAISON=nouvelle\nAUTRE=x\nHUE_KEY_CHALET=abc\n"
    )


def test_update_env_file_creates_missing_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"

    update_env_file(env, {"HUE_KEY_MAISON": "abc"})

    assert env.read_text(encoding="utf-8") == "HUE_KEY_MAISON=abc\n"
