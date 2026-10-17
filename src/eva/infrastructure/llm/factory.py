"""Construction du fournisseur de LLM à partir de la configuration."""

from pydantic import ValidationError

from eva.application.llm import LLMProvider
from eva.config import LlmSettings
from eva.domain import ConfigurationError


def create_provider(settings: LlmSettings) -> LLMProvider:
    """Instancie le fournisseur choisi par `[llm] provider`.

    Ajouter un fournisseur = une implémentation de `LLMProvider` dans ce paquet
    + une branche ici.
    """
    match settings.provider:
        case "ollama":
            from eva.infrastructure.llm.ollama import DEFAULT_MODEL, OllamaConfig, OllamaProvider

            try:
                config = OllamaConfig.model_validate(settings.section("ollama"))
            except ValidationError as e:
                raise ConfigurationError(f"Section [llm.ollama] invalide :\n{e}") from e
            return OllamaProvider(
                config, model=settings.model or DEFAULT_MODEL, max_tokens=settings.max_tokens
            )
        case None:
            raise ConfigurationError(
                "Aucun fournisseur de LLM configuré : renseignez [llm] provider dans eva.toml."
            )
        case unknown:
            raise ConfigurationError(f"Fournisseur de LLM inconnu : {unknown}")
