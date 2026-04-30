from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from plugins.contracts import GeneratorPlugin, PluginManifest, PluginPermissions, ReviewerPlugin, TesterPlugin


@dataclass(frozen=True)
class PluginCapabilityPolicy:
    allow_workspace_write: bool = True
    allow_sandbox_exec: bool = False
    allow_network_access: bool = False

    def denial_reasons(self, permissions: PluginPermissions) -> tuple[str, ...]:
        reasons: list[str] = []
        if permissions.workspace_write and not self.allow_workspace_write:
            reasons.append("workspace_write_not_allowed")
        if permissions.sandbox_exec and not self.allow_sandbox_exec:
            reasons.append("sandbox_exec_not_allowed")
        if permissions.network_access and not self.allow_network_access:
            reasons.append("network_access_not_allowed")
        return tuple(reasons)

    def is_allowed(self, permissions: PluginPermissions) -> bool:
        return not self.denial_reasons(permissions)


@dataclass(frozen=True)
class PluginPolicy:
    default_deny: bool
    global_allow: frozenset[str]
    environment_allow: dict[str, frozenset[str]]
    project_allow: dict[str, frozenset[str]]
    capability_policy: PluginCapabilityPolicy = field(default_factory=PluginCapabilityPolicy)

    def is_allowed(self, plugin_id: str, *, environment: str = "", project_id: str = "") -> bool:
        safe_environment = (environment or "").strip().lower()
        safe_project_id = (project_id or "").strip()
        if plugin_id in self.global_allow or "*" in self.global_allow:
            return True
        if safe_environment:
            env_allow = self.environment_allow.get(safe_environment, frozenset())
            if plugin_id in env_allow or "*" in env_allow:
                return True
        if safe_project_id:
            project_allow = self.project_allow.get(safe_project_id, frozenset())
            if plugin_id in project_allow or "*" in project_allow:
                return True
        return not self.default_deny

    def is_capability_allowed(self, permissions: PluginPermissions) -> bool:
        return self.capability_policy.is_allowed(permissions)

    def capability_denial_reasons(self, permissions: PluginPermissions) -> tuple[str, ...]:
        return self.capability_policy.denial_reasons(permissions)


class PluginLoader:
    def __init__(
        self,
        plugin_dir: str | Path | None = None,
        allowlist_file: str | Path | None = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parent
        self.plugin_dir = Path(plugin_dir).resolve(strict=False) if plugin_dir else base_dir
        self.allowlist_file = (
            Path(allowlist_file).resolve(strict=False)
            if allowlist_file
            else self.plugin_dir / "allowlist.json"
        )

    def load_reviewer_plugins(self) -> list[ReviewerPlugin]:
        return [plugin for plugin in self._load_plugins() if plugin.manifest.plugin_type == "reviewer"]

    def load_generator_plugins(self) -> list[GeneratorPlugin]:
        return [plugin for plugin in self._load_plugins() if plugin.manifest.plugin_type == "generator"]

    def load_tester_plugins(self) -> list[TesterPlugin]:
        return [plugin for plugin in self._load_plugins() if plugin.manifest.plugin_type == "tester"]

    def _load_plugins(self) -> list[Any]:
        plugins: list[Any] = []
        for manifest_path in sorted(self.plugin_dir.glob("*_agent.manifest.json")):
            manifest = self._read_manifest(manifest_path)
            if not manifest.enabled:
                continue
            plugins.append(self._instantiate_plugin(manifest))
        return plugins

    def read_policy(self) -> PluginPolicy:
        raw = os.getenv("MVP_PLUGIN_ALLOWLIST", "").strip()
        if raw:
            allowlist = frozenset(item.strip() for item in raw.split(",") if item.strip())
            return PluginPolicy(
                default_deny=True,
                global_allow=allowlist,
                environment_allow={},
                project_allow={},
                capability_policy=PluginCapabilityPolicy(),
            )
        if not self.allowlist_file.exists():
            return PluginPolicy(
                default_deny=True,
                global_allow=frozenset(),
                environment_allow={},
                project_allow={},
                capability_policy=PluginCapabilityPolicy(),
            )
        payload = json.loads(self.allowlist_file.read_text(encoding="utf-8"))
        capability_policy = payload.get("capability_policy") or {}
        return PluginPolicy(
            default_deny=bool(payload.get("default_deny", True)),
            global_allow=frozenset(_normalize_text_list(payload.get("global_allow"))),
            environment_allow=_normalize_scope_mapping(payload.get("environment_allow")),
            project_allow=_normalize_scope_mapping(payload.get("project_allow")),
            capability_policy=PluginCapabilityPolicy(
                allow_workspace_write=bool(capability_policy.get("allow_workspace_write", True)),
                allow_sandbox_exec=bool(capability_policy.get("allow_sandbox_exec", False)),
                allow_network_access=bool(capability_policy.get("allow_network_access", False)),
            ),
        )

    def _read_manifest(self, manifest_path: Path) -> PluginManifest:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        plugin_id = str(payload.get("plugin_id", "")).strip()
        version = str(payload.get("version", "")).strip() or "0.1.0"
        plugin_type = str(payload.get("plugin_type", "")).strip().lower()
        entrypoint = str(payload.get("entrypoint", "")).strip()
        class_name = str(payload.get("class_name", "")).strip()
        if not plugin_id or not entrypoint or not class_name:
            raise ValueError(f"invalid plugin manifest: {manifest_path}")
        permissions = payload.get("permissions") or {}
        return PluginManifest(
            plugin_id=plugin_id,
            version=version,
            plugin_type=plugin_type,  # type: ignore[arg-type]
            entrypoint=entrypoint,
            class_name=class_name,
            enabled=bool(payload.get("enabled", True)),
            priority=int(payload.get("priority", 100)),
            capabilities=tuple(_normalize_text_list(payload.get("capabilities"))),
            supported_intents=tuple(_normalize_text_list(payload.get("supported_intents"))),
            supported_assistants=tuple(_normalize_text_list(payload.get("supported_assistants"))),
            timeout_seconds=max(1, int(payload.get("timeout_seconds", 15))),
            permissions=PluginPermissions(
                workspace_read=bool(permissions.get("workspace_read", True)),
                workspace_write=bool(permissions.get("workspace_write", False)),
                sandbox_exec=bool(permissions.get("sandbox_exec", False)),
                network_access=bool(permissions.get("network_access", False)),
            ),
            source_path=manifest_path,
        )

    def _instantiate_plugin(self, manifest: PluginManifest) -> ReviewerPlugin:
        source_path = self._resolve_plugin_source_path(manifest)
        if not source_path.exists():
            raise FileNotFoundError(f"plugin source not found: {source_path}")
        module_name = f"autocode_plugin_{manifest.plugin_id.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, source_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load plugin module: {source_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plugin_cls = getattr(module, manifest.class_name, None)
        if plugin_cls is None:
            raise AttributeError(f"plugin class not found: {manifest.class_name}")
        plugin = plugin_cls()
        setattr(plugin, "manifest", manifest)
        return plugin

    def _resolve_plugin_source_path(self, manifest: PluginManifest) -> Path:
        raw_entrypoint = Path(manifest.entrypoint)
        if raw_entrypoint.is_absolute():
            raise PermissionError(f"plugin entrypoint must be relative: {manifest.entrypoint}")
        source_path = (self.plugin_dir / raw_entrypoint).resolve(strict=False)
        if not _is_relative_to(source_path, self.plugin_dir):
            raise PermissionError(f"plugin entrypoint escapes plugin directory: {manifest.entrypoint}")
        if source_path.name and not source_path.name.endswith("_agent.py"):
            raise PermissionError(f"plugin entrypoint must target *_agent.py: {manifest.entrypoint}")
        return source_path


def _normalize_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_scope_mapping(value: Any) -> dict[str, frozenset[str]]:
    if not isinstance(value, dict):
        return {}
    output: dict[str, frozenset[str]] = {}
    for key, raw_items in value.items():
        safe_key = str(key).strip().lower() if value is not None else ""
        if not safe_key:
            continue
        output[safe_key] = frozenset(_normalize_text_list(raw_items))
    return output


def _is_relative_to(path: Path, candidate_parent: Path) -> bool:
    try:
        path.relative_to(candidate_parent)
        return True
    except ValueError:
        return False
