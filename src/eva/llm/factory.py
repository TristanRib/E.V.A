"""Construction du fournisseur de LLM à partir de la configuration."""

from eva.config import EvaSettings
from eva.domain import ConfigurationError
from eva.llm.provider import LLMProvider


def create_provider(settings: EvaSettings) -> LLMProvider:
    """Instancie le fournisseur choisi par `EVA_PROVIDER`.

    Ajouter un fournisseur = une implémentation de `LLMProvider` dans `providers/`
    + une branche ici.
    """
    match settings.provider:
        case "ollama":
            from eva.llm.providers.ollama import DEFAULT_MODEL, OllamaProvider, OllamaSettings

            return OllamaProvider(
                OllamaSettings(),
                model=settings.model or DEFAULT_MODEL,
                max_tokens=settings.max_tokens,
            )
        case None:
            raise ConfigurationError(
                "Aucun fournisseur de LLM configuré : renseignez EVA_PROVIDER dans .env."
            )
        case unknown:
            raise ConfigurationError(f"Fournisseur de LLM inconnu : {unknown}")
