"""Contrat d'un plugin : un paquet autonome qui apporte des outils à E.V.A."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from eva.application import ToolRunner
from eva.config import Secrets
from eva.domain import EvaError, Tool


class PluginUnavailable(EvaError):
    """Le plugin ne peut pas être activé (non configuré, service injoignable…)."""


class NoConfig(BaseModel):
    """Configuration d'un plugin qui n'en a pas."""

    model_config = ConfigDict(extra="ignore")


@dataclass(frozen=True, slots=True)
class PluginContext[ConfigT: BaseModel]:
    """Tout ce que E.V.A met à disposition d'un plugin.

    Les besoins futurs (notifications, planificateur…) s'ajouteront ici, sans changer
    la signature de `Plugin.setup` ni toucher aux plugins existants.
    """

    config: ConfigT
    """Section `[plugins.<nom>]` d'`eva.toml`, déjà validée."""
    secrets: Secrets
    resources: AsyncExitStack
    """Ressources à libérer à l'arrêt (connexions…)."""
    tools: ToolRunner
    """Exécution des outils de tous les plugins, disponible une fois E.V.A démarrée."""


class Plugin[ConfigT: BaseModel](ABC):
    """Une capacité d'E.V.A : déclare sa configuration et fournit ses outils.

    Son nom est sa clé dans `plugins/registry.py::PLUGINS`.
    """

    config_model: type[ConfigT]

    @abstractmethod
    async def setup(self, context: PluginContext[ConfigT]) -> Sequence[Tool[Any]]:
        """Prépare le plugin et renvoie ses outils.

        Raises:
            PluginUnavailable: le plugin ne peut pas fonctionner pour l'instant.
        """
