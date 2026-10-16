"""Contrat d'un plugin : un paquet autonome qui apporte des outils à E.V.A."""

from collections.abc import Sequence
from contextlib import AsyncExitStack
from typing import Any, Protocol

from eva.domain import EvaError, Tool


class PluginUnavailable(EvaError):
    """Le plugin ne peut pas être activé (non configuré, service injoignable…)."""


class Plugin(Protocol):
    """Une capacité d'E.V.A : lit ses propres réglages et fournit ses outils."""

    @property
    def name(self) -> str:
        """Identifiant court, utilisé par `EVA_PLUGINS`."""
        ...

    async def create_tools(self, resources: AsyncExitStack) -> Sequence[Tool[Any]]:
        """Prépare le plugin et renvoie ses outils.

        Les ressources à libérer à l'arrêt (connexions…) s'enregistrent dans `resources`.

        Raises:
            PluginUnavailable: le plugin ne peut pas fonctionner pour l'instant.
        """
        ...
