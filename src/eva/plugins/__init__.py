"""Plugins : chaque capacité d'E.V.A est un paquet autonome qui fournit ses outils."""

from eva.plugins.base import Plugin, PluginUnavailable
from eva.plugins.registry import PLUGINS, load_plugins

__all__ = ["PLUGINS", "Plugin", "PluginUnavailable", "load_plugins"]
