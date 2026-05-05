from __future__ import annotations

from plugins.contracts import GeneratorPlugin, PluginContext, ReviewerPlugin, TesterPlugin
from plugins.loader import PluginLoader, PluginPolicy
from plugins.runtime import PluginRuntimeManager


class PluginRegistry:
    def __init__(
        self,
        loader: PluginLoader | None = None,
        runtime_manager: PluginRuntimeManager | None = None,
    ) -> None:
        self.loader = loader or PluginLoader()
        self.policy = self.loader.read_policy()
        self.runtime = runtime_manager or PluginRuntimeManager()
        self._reviewer_plugins = sorted(
            self.loader.load_reviewer_plugins(),
            key=lambda item: int(getattr(item.manifest, "priority", 100)),
        )
        self._generator_plugins = sorted(
            self.loader.load_generator_plugins(),
            key=lambda item: int(getattr(item.manifest, "priority", 100)),
        )
        self._tester_plugins = sorted(
            self.loader.load_tester_plugins(),
            key=lambda item: int(getattr(item.manifest, "priority", 100)),
        )

    def resolve_reviewer_plugins(self, context: PluginContext) -> list[ReviewerPlugin]:
        output: list[ReviewerPlugin] = []
        for plugin in self._reviewer_plugins:
            manifest = plugin.manifest
            if not self._is_allowed_for_context(manifest.plugin_id, context):
                continue
            if not self.policy.is_capability_allowed(manifest.permissions):
                continue
            if manifest.supported_intents and context.task.get("intent") not in manifest.supported_intents:
                continue
            assistant = _resolve_assistant(context)
            if manifest.supported_assistants and assistant not in manifest.supported_assistants:
                continue
            if plugin.supports(context):
                output.append(plugin)
        return output

    def resolve_generator_plugins(self, context: PluginContext, *, target: str) -> list[GeneratorPlugin]:
        output: list[GeneratorPlugin] = []
        normalized_target = (target or "").strip().lower()
        for plugin in self._generator_plugins:
            manifest = plugin.manifest
            if not self._is_allowed_for_context(manifest.plugin_id, context):
                continue
            if not self.policy.is_capability_allowed(manifest.permissions):
                continue
            if manifest.supported_intents and context.task.get("intent") not in manifest.supported_intents:
                continue
            capabilities = {item.strip().lower() for item in manifest.capabilities}
            if normalized_target and f"target:{normalized_target}" not in capabilities:
                continue
            assistant = _resolve_assistant(context)
            if manifest.supported_assistants and assistant not in manifest.supported_assistants:
                continue
            if plugin.supports(context):
                output.append(plugin)
        return output

    def resolve_tester_plugins(self, context: PluginContext) -> list[TesterPlugin]:
        output: list[TesterPlugin] = []
        for plugin in self._tester_plugins:
            manifest = plugin.manifest
            if not self._is_allowed_for_context(manifest.plugin_id, context):
                continue
            if not self.policy.is_capability_allowed(manifest.permissions):
                continue
            if manifest.supported_intents and context.task.get("intent") not in manifest.supported_intents:
                continue
            assistant = _resolve_assistant(context)
            if manifest.supported_assistants and assistant not in manifest.supported_assistants:
                continue
            if plugin.supports(context):
                output.append(plugin)
        return output

    def _is_allowed_for_context(self, plugin_id: str, context: PluginContext) -> bool:
        environment = _resolve_environment(context)
        project_id = _resolve_project_id(context)
        return self.policy.is_allowed(plugin_id, environment=environment, project_id=project_id)

    def execute_plugin(self, plugin_id: str, operation):
        return self.runtime.execute(plugin_id, operation)

    def plugin_state(self, plugin_id: str) -> dict[str, object]:
        return self.runtime.state(plugin_id)


def _resolve_assistant(context: PluginContext) -> str:
    assistant = str(context.task.get("assistant", "")).strip().lower()
    return assistant or "ai-agent"


def _resolve_environment(context: PluginContext) -> str:
    env = str(context.task.get("environment") or context.task.get("env") or "").strip().lower()
    if env:
        return env
    return "default"


def _resolve_project_id(context: PluginContext) -> str:
    for key in ("projectId", "projectKey", "project_id"):
        value = str(context.task.get(key, "")).strip()
        if value:
            return value
    return ""
