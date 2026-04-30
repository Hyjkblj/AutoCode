from __future__ import annotations

from generators.backend_generator import BackendGenerator
from plugins.contracts import PluginContext


class BackendTemplateGeneratorAgent:
    manifest = None

    def __init__(self) -> None:
        self.backend_generator = BackendGenerator()

    def supports(self, context: PluginContext) -> bool:
        target = str(context.task.get("target", "")).strip().lower()
        generated_target = str(context.task.get("_requestedGenerationTarget", "")).strip().lower()
        normalized_target = generated_target or target
        return normalized_target == "backend"

    def generate(self, context: PluginContext):
        result = self.backend_generator.generate(str(context.task.get("prompt", "")).strip())
        context.publish_event(
            {
                "stage": "GeneratorPlugin",
                "message": "Generator plugin completed.",
                "pluginId": context.task.get("_activeGeneratorPlugin"),
                "target": "backend",
                "fallbackUsed": result.used_fallback,
                "reason": result.reason,
                "fileCount": len(result.files),
            }
        )
        return result
