"""Utilitaires de texte."""

import unicodedata


def normalize(text: str) -> str:
    """Forme comparable d'un texte : minuscules, sans accents ni espaces superflus."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())
