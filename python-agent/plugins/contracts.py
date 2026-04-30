from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from agents.planner_agent import PlanResult
from agents.reviewer_agent import EventPublisher, ReviewResult
from client.control_plane_client import ControlPlaneClient
from generators import GeneratedProjectResult

PluginType = Literal["reviewer", "generator", "tester"]


@dataclass(frozen=True)
class PluginPermissions:
    workspace_read: bool = True
    workspace_write: bool = False
    sandbox_exec: bool = False
    network_access: bool = False


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    version: str
    plugin_type: PluginType
    entrypoint: str
    class_name: str
    enabled: bool = True
    priority: int = 100
    capabilities: tuple[str, ...] = ()
    supported_intents: tuple[str, ...] = ()
    supported_assistants: tuple[str, ...] = ()
    timeout_seconds: int = 15
    permissions: PluginPermissions = field(default_factory=PluginPermissions)
    source_path: Path | None = None


@dataclass(frozen=True)
class PluginContext:
    task: dict[str, Any]
    client: ControlPlaneClient
    plan: PlanResult
    publish_event: EventPublisher


class ReviewerPlugin(Protocol):
    manifest: PluginManifest

    def supports(self, context: PluginContext) -> bool:
        ...

    def review(self, context: PluginContext) -> ReviewResult:
        ...


class GeneratorPlugin(Protocol):
    manifest: PluginManifest

    def supports(self, context: PluginContext) -> bool:
        ...

    def generate(self, context: PluginContext) -> GeneratedProjectResult:
        ...


class TesterPlugin(Protocol):
    manifest: PluginManifest

    def supports(self, context: PluginContext) -> bool:
        ...

    def resolve_command(self, context: PluginContext) -> str:
        ...
