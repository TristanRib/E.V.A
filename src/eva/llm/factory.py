"""Construction du fournisseur de LLM à partir de la configuration."""

from pydantic import ValidationError

from eva.config import LlmSettings
from eva.domain import ConfigurationError
from eva.llm.provider import LLMProvider


def create_provider(settings: LlmSettings) -> LLMProvider:
    """Instancie le fournisseur choisi par `[llm] provider`.

    Ajouter un fournisseur = une implémentation de `LLMProvider` dans `providers/`
    + une branche ici.
    """
    match settings.provider:
        case "ollama":
            from eva.llm.providers.ollama import DEFAULT_MODEL, OllamaConfig, OllamaProvider

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
