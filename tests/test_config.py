from pathlib import Path

import pytest

from eva.config import EvaSettings, Secrets

TOML = """\
user_name = "Alice"
log_level = "info"

[llm]
provider = "ollama"
model = "petit-modele"

[llm.ollama]
host = "http://ailleurs:11434"

[plugins]
enabled = ["clock"]

[[plugins.hue.homes]]
name = "Maison"
bridge_ip = "192.168.1.10"
"""


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "eva.toml"
    path.write_text(TOML, encoding="utf-8")
    monkeypatch.setenv("EVA_CONFIG", str(path))
    for name in ("EVA_LOG_LEVEL", "EVA_LLM__MODEL", "EVA_USER_NAME"):
        monkeypatch.delenv(name, raising=False)
    return path


def test_reads_core_settings_from_toml(config_file: Path) -> None:
    settings = EvaSettings()

    assert settings.user_name == "Alice"
    assert settings.log_level == "INFO"
    assert settings.llm.provider == "ollama"
    assert settings.plugins.enabled == ["clock"]


def test_component_sections_stay_raw(config_file: Path) -> None:
    settings = EvaSettings()

    assert settings.llm.section("ollama") == {"host": "http://ailleurs:11434"}
    assert settings.plugins.section("hue") == {
        "homes": [{"name": "Maison", "bridge_ip": "192.168.1.10"}]
    }
    assert settings.plugins.section("absent") == {}


def test_environment_overrides_toml_without_erasing_siblings(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EVA_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("EVA_LLM__MODEL", "autre-modele")

    settings = EvaSettings()

    assert settings.log_level == "DEBUG"
    assert settings.llm.model == "autre-modele"
    assert settings.llm.provider == "ollama"
    assert settings.llm.section("ollama") == {"host": "http://ailleurs:11434"}


def test_missing_file_gives_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVA_CONFIG", str(tmp_path / "absent.toml"))

    settings = EvaSettings()

    assert settings.llm.provider is None
    assert settings.plugins.enabled is None


def test_secrets_prefer_environment_over_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("HUE_KEY_MAISON=depuis-fichier\nVIDE=\nAUTRE=fichier\n", encoding="utf-8")
    monkeypatch.setenv("AUTRE", "environnement")

    secrets = Secrets.load(dotenv)

    assert secrets.get("HUE_KEY_MAISON") is not None
    assert secrets.get("HUE_KEY_MAISON").get_secret_value() == "depuis-fichier"  # type: ignore[union-attr]
    assert secrets.get("AUTRE").get_secret_value() == "environnement"  # type: ignore[union-attr]
    assert secrets.get("VIDE") is None
    assert secrets.get("INCONNU") is None
