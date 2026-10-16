"""Hiérarchie des erreurs d'E.V.A."""


class EvaError(Exception):
    """Erreur attendue d'E.V.A, dont le message est destiné à l'utilisateur."""


class ConfigurationError(EvaError):
    """Configuration absente ou invalide."""


class ToolError(EvaError):
    """Échec attendu d'un outil : son message est transmis tel quel au LLM."""
