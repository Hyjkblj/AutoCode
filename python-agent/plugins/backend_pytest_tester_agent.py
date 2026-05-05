from __future__ import annotations

from plugins.contracts import PluginContext


class BackendPytestTesterAgent:
    manifest = None

    def supports(self, context: PluginContext) -> bool:
        generated_target = str(context.task.get("_generated_target", "")).strip().lower()
        explicit_target = str(context.task.get("target", "")).strip().lower()
        normalized_target = generated_target or explicit_target
        return normalized_target == "backend"

    def resolve_command(self, context: PluginContext) -> str:
        context.publish_event(
            {
                "stage": "TesterPlugin",
                "message": "Tester plugin selected validation command.",
                "pluginId": context.task.get("_activeTesterPlugin"),
                "command": "pytest -q",
                "target": "backend",
            }
        )
        return "pytest -q"
