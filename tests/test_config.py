from pathlib import Path

import pytest

from eva.config import EvaSettings, Secrets

TOML = """\
user_name = "Alice"
log_level = "info"

[llm]
provider = "fournisseur"
model = "petit-modele"

[llm.fournisseur]
url = "http://ailleurs:1234"

[plugins]
enabled = ["exemple"]

[[plugins.exemple.comptes]]
nom = "Principal"
identifiant = "alice"
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
    assert settings.llm.provider == "fournisseur"
    assert settings.plugins.enabled == ["exemple"]


def test_component_sections_stay_raw(config_file: Path) -> None:
    settings = EvaSettings()

    assert settings.llm.section("fournisseur") == {"url": "http://ailleurs:1234"}
    assert settings.plugins.section("exemple") == {
        "comptes": [{"nom": "Principal", "identifiant": "alice"}]
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
    assert settings.llm.provider == "fournisseur"
    assert settings.llm.section("fournisseur") == {"url": "http://ailleurs:1234"}


def test_missing_file_gives_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVA_CONFIG", str(tmp_path / "absent.toml"))

    settings = EvaSettings()

    assert settings.llm.provider is None
    assert settings.plugins.enabled is None


def test_secrets_prefer_environment_over_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("API_KEY=depuis-fichier\nVIDE=\nAUTRE=fichier\n", encoding="utf-8")
    monkeypatch.setenv("AUTRE", "environnement")

    secrets = Secrets.load(dotenv)

    assert secrets.get("API_KEY") is not None
    assert secrets.get("API_KEY").get_secret_value() == "depuis-fichier"  # type: ignore[union-attr]
    assert secrets.get("AUTRE").get_secret_value() == "environnement"  # type: ignore[union-attr]
    assert secrets.get("VIDE") is None
    assert secrets.get("INCONNU") is None
