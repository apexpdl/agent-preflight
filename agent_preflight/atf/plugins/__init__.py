"""Built-in simulation plugins for common risk domains."""

from agent_preflight.atf.plugins.filesystem import FilesystemCascadePlugin
from agent_preflight.atf.plugins.api_cost import APICostExplosionPlugin
from agent_preflight.atf.plugins.dependency import DependencyGraphPlugin
from agent_preflight.atf.plugins.memory import MemoryRunawayPlugin
from agent_preflight.atf.plugins.infrastructure import InfrastructureMutationPlugin

ALL_PLUGINS = [
    FilesystemCascadePlugin,
    APICostExplosionPlugin,
    DependencyGraphPlugin,
    MemoryRunawayPlugin,
    InfrastructureMutationPlugin,
]

__all__ = [
    "FilesystemCascadePlugin",
    "APICostExplosionPlugin",
    "DependencyGraphPlugin",
    "MemoryRunawayPlugin",
    "InfrastructureMutationPlugin",
    "ALL_PLUGINS",
]
