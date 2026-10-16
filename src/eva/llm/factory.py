"""Construction du fournisseur de LLM à partir de la configuration."""

from eva.config import Settings
from eva.llm.base import LLMError, LLMProvider


def create_provider(settings: Settings) -> LLMProvider:
    """Instancie le fournisseur choisi par `EVA_PROVIDER`.

    Ajouter un fournisseur = une implémentation de `LLMProvider` + une branche ici.
    """
    match settings.provider:
        case "ollama":
            from eva.llm.ollama import DEFAULT_MODEL, OllamaProvider

            return OllamaProvider(
                model=settings.model or DEFAULT_MODEL,
                host=settings.ollama_host,
                max_tokens=settings.max_tokens,
                context_size=settings.context_size,
                keep_alive=settings.keep_alive,
            )
        case None:
            raise LLMError("Aucun fournisseur de LLM configuré : renseigne EVA_PROVIDER dans .env.")
        case unknown:
            raise LLMError(f"Fournisseur de LLM inconnu : {unknown}")
