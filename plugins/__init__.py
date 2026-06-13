"""插件系统"""
from plugins.manifest import PluginManifest, parse_manifest
from plugins.discovery import discover_plugins, DiscoveredPlugin
from plugins.manager import PluginManager, PluginState, PluginRecord

__all__ = [
    "PluginManifest", "parse_manifest", "discover_plugins", "DiscoveredPlugin",
    "PluginManager", "PluginState", "PluginRecord",
]
