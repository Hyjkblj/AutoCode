from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Any

from agents.planner_agent import PlanResult
from client.control_plane_client import ControlPlaneClient
from generators import GeneratedProjectResult
from generators.backend_generator import BackendGenerator
from generators.fullstack_generator import FullstackGenerator
from llm.llm_client import LLMClient
from plugins.contracts import PluginContext
from plugins.registry import PluginRegistry
from tools.code_index import CodeIndex
from tools.file_tool import FileTool
from tools.git_tool import GitTool
from tools.search_tool import SearchTool
from utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from utils.observability import ensure_task_observability
from utils.web_template import WebTemplateGenerator


class CoderAgent:
    def __init__(
        self,
        file_tool: FileTool | None = None,
        search_tool: SearchTool | None = None,
        web_template_generator: WebTemplateGenerator | None = None,
        backend_generator: BackendGenerator | None = None,
        fullstack_generator: FullstackGenerator | None = None,
        llm_client: LLMClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        plugin_registry: PluginRegistry | None = None,
        code_index: CodeIndex | None = None,
        git_tool: GitTool | None = None,
    ) -> None:
        self.file_tool = file_tool or FileTool()
        self.search_tool = search_tool or SearchTool()
        self.web_template_generator = web_template_generator or WebTemplateGenerator()
        self.backend_generator = backend_generator or BackendGenerator()
        self.fullstack_generator = fullstack_generator or FullstackGenerator(
            backend_generator=self.backend_generator,
            web_template_generator=self.web_template_generator,
        )
        self.llm_client = llm_client or LLMClient()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(name="coder-llm")
        self.plugin_registry = plugin_registry or PluginRegistry()
        self.code_index = code_index
        self.git_tool = git_tool

    def execute(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publish_event: EventPublisher,
    ) -> bool:
        workspace = self._resolve_workspace(task)
        prompt = str(task.get("prompt", "")).strip()
        target = str(task.get("target", "")).strip().lower()
        assistant = str(task.get("assistant", "")).strip().lower()
        generation_target = self._resolve_generation_target(target=target, assistant=assistant, prompt=prompt)
        if generation_target is not None:
            task["_requestedGenerationTarget"] = generation_target

        if generation_target is not None:
            return self._generate_project(
                task=task,
                client=client,
                plan=plan,
                publish_event=publish_event,
                workspace=workspace,
                prompt=prompt,
                generation_target=generation_target,
            )

        try:
            target_file = self._choose_target_file(workspace, prompt)
            existed_before = target_file.exists()
            before = self.file_tool.read_text(target_file) if existed_before else ""
            after = self._propose_content(before=before, prompt=prompt, task=task, target_file=target_file)
            self.file_tool.write_text(target_file, after)
        except PermissionError as exc:
            publish_event(
                {
                    "stage": "CoderAgent",
                    "message": "Write blocked by workspace allowlist.",
                    "error": str(exc),
                }
            )
            publish_event({"reason": "path_not_allowed", "detail": str(exc)}, event_type="TASK_FAILED")
            return False
        except Exception as exc:  # noqa: BLE001
            publish_event(
                {
                    "stage": "CoderAgent",
                    "message": "Failed to prepare code change.",
                    "error": str(exc),
                }
            )
            publish_event({"reason": "coder_error", "detail": str(exc)}, event_type="TASK_FAILED")
            return False

        relative = self._relative_path(target_file, workspace)
        patch = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{relative}",
                tofile=f"b/{relative}",
            )
        )
        publish_event(
            {
                "stage": "CoderAgent",
                "message": "Code change prepared.",
                "file": relative,
                "planName": plan.plan_name,
            }
        )
        publish_event(
            {
                "format": "unified",
                "patch": patch,
                "files": [{"path": relative, "changeType": "modify" if existed_before else "add"}],
            },
            event_type="FILE_PATCH_PREVIEW",
        )
        return True

    @staticmethod
    def _resolve_generation_target(*, target: str, assistant: str, prompt: str) -> str | None:
        normalized_target = (target or "").strip().lower()
        if normalized_target in {"web", "backend", "fullstack"}:
            return normalized_target

        normalized_assistant = (assistant or "").strip().lower()
        if normalized_assistant in {"web", "website"}:
            return "web"

        text = (prompt or "").strip().lower()
        if not text:
            return None
        if not CoderAgent._looks_like_generation_request(text):
            return "web" if CoderAgent._should_generate_web(prompt=text) else None
        if any(marker in text for marker in ("fullstack", "全栈", "前后端")):
            return "fullstack"
        if any(marker in text for marker in ("backend", "api service", "flask app", "fastapi", "后端", "接口服务")):
            return "backend"
        if CoderAgent._should_generate_web(prompt=text):
            return "web"
        return None

    @staticmethod
    def _should_generate_project(*, target: str, assistant: str, prompt: str) -> bool:
        return CoderAgent._resolve_generation_target(target=target, assistant=assistant, prompt=prompt) is not None

    @staticmethod
    def _should_generate_web(prompt: str) -> bool:
        strong_web_markers = (
            "website",
            "web page",
            "webapp",
            "landing page",
            "dashboard",
            "calculator",
            "todo",
            "weather",
            "portfolio",
            "gallery",
            "form",
            "html",
            "css",
            "javascript",
            "网页",
            "页面",
            "仪表盘",
            "计算器",
            "待办",
            "天气",
            "展示",
            "表单",
            "管理系统",
        )
        if any(marker in prompt for marker in strong_web_markers):
            return True

        action_markers = ("generate", "build", "create", "make", "生成", "搭建", "做一个", "做个")
        weak_web_markers = ("web", "网站", "应用")
        return any(action in prompt for action in action_markers) and any(marker in prompt for marker in weak_web_markers)

    @staticmethod
    def _looks_like_generation_request(prompt: str) -> bool:
        action_markers = (
            "generate",
            "build",
            "create",
            "make",
            "scaffold",
            "bootstrap",
            "new project",
            "from scratch",
            "鐢熸垚",
            "鎼缓",
            "鏂板缓",
        )
        return any(marker in prompt for marker in action_markers)

    def _generate_project(
        self,
        *,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publish_event: EventPublisher,
        workspace: Path,
        prompt: str,
        generation_target: str,
    ) -> bool:
        try:
            template = self._resolve_generation_template(
                task=task,
                client=client,
                plan=plan,
                publish_event=publish_event,
                generation_target=generation_target,
                prompt=prompt,
            )

            task["_generated_target"] = generation_target
            task["_generated_files"] = list(template.files.keys())
            task["_llm_fallback"] = bool(template.used_fallback)
            task["_llm_generation_reason"] = template.reason

            changed_files: list[dict[str, Any]] = []
            for relative, content in template.files.items():
                target_path = workspace / relative
                existed_before = target_path.exists()
                before = self.file_tool.read_text(target_path) if existed_before else ""
                if before == content:
                    continue
                self.file_tool.write_text(target_path, content)
                patch = "".join(
                    difflib.unified_diff(
                        before.splitlines(keepends=True),
                        content.splitlines(keepends=True),
                        fromfile=f"a/{relative}",
                        tofile=f"b/{relative}",
                    )
                )
                change_type = "modify" if existed_before else "add"
                changed_files.append({"path": relative, "changeType": change_type})
                publish_event(
                    {
                        "format": "unified",
                        "patch": patch,
                        "files": [{"path": relative, "changeType": change_type}],
                    },
                    event_type="FILE_PATCH_PREVIEW",
                )

            if not changed_files:
                publish_event(
                    {
                        "stage": "CoderAgent",
                        "message": "Project generation produced no file changes.",
                        "planName": plan.plan_name,
                        "target": generation_target,
                        "fallbackUsed": template.used_fallback,
                        "reason": template.reason,
                    }
                )
                return True

            publish_event(
                {
                    "stage": "CoderAgent",
                    "message": "Project template generated.",
                    "planName": plan.plan_name,
                    "target": generation_target,
                    "fileCount": len(changed_files),
                    "fallbackUsed": template.used_fallback,
                    "reason": template.reason,
                }
            )
            return True
        except PermissionError as exc:
            publish_event(
                {
                    "stage": "CoderAgent",
                    "message": "Write blocked by workspace allowlist.",
                    "error": str(exc),
                }
            )
            publish_event({"reason": "path_not_allowed", "detail": str(exc)}, event_type="TASK_FAILED")
            return False
        except Exception as exc:  # noqa: BLE001
            publish_event(
                {
                    "stage": "CoderAgent",
                    "message": "Failed to generate project.",
                    "error": str(exc),
                    "target": generation_target,
                }
            )
            publish_event({"reason": "generation_failed", "detail": str(exc)}, event_type="TASK_FAILED")
            return False

    def _resolve_generation_template(
        self,
        *,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publish_event: EventPublisher,
        generation_target: str,
        prompt: str,
    ) -> GeneratedProjectResult:
        task.setdefault("intent", "code_change")
        plugin_context = PluginContext(task=task, client=client, plan=plan, publish_event=publish_event)
        plugins = self.plugin_registry.resolve_generator_plugins(plugin_context, target=generation_target)
        for plugin in plugins:
            manifest = plugin.manifest
            task["_activeGeneratorPlugin"] = manifest.plugin_id
            breaker_state = self.plugin_registry.plugin_state(manifest.plugin_id)
            publish_event(
                {
                    "stage": "GeneratorPlugin",
                    "message": "Executing generator plugin.",
                    "pluginId": manifest.plugin_id,
                    "pluginVersion": manifest.version,
                    "target": generation_target,
                    "breakerStatus": breaker_state.get("status"),
                    "failureCount": breaker_state.get("failureCount"),
                    "permissions": {
                        "workspaceRead": manifest.permissions.workspace_read,
                        "workspaceWrite": manifest.permissions.workspace_write,
                        "sandboxExec": manifest.permissions.sandbox_exec,
                        "networkAccess": manifest.permissions.network_access,
                    },
                }
            )
            try:
                return self.plugin_registry.execute_plugin(
                    manifest.plugin_id,
                    lambda: plugin.generate(plugin_context),
                )
            except CircuitBreakerOpenError:
                breaker_state = self.plugin_registry.plugin_state(manifest.plugin_id)
                publish_event(
                    {
                        "stage": "GeneratorPlugin",
                        "message": "Plugin skipped due to circuit breaker, falling back to built-in implementation.",
                        "pluginId": manifest.plugin_id,
                        "target": generation_target,
                        "breakerStatus": breaker_state.get("status"),
                        "failureCount": breaker_state.get("failureCount"),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                breaker_state = self.plugin_registry.plugin_state(manifest.plugin_id)
                publish_event(
                    {
                        "stage": "GeneratorPlugin",
                        "message": "Generator plugin failed, falling back to built-in generator.",
                        "pluginId": manifest.plugin_id,
                        "target": generation_target,
                        "breakerStatus": breaker_state.get("status"),
                        "failureCount": breaker_state.get("failureCount"),
                        "error": str(exc),
                    }
                )
        task.pop("_activeGeneratorPlugin", None)

        if generation_target == "web":
            return self.web_template_generator.generate(prompt, target="web", task=task)
        if generation_target == "backend":
            return self.backend_generator.generate(prompt)
        if generation_target == "fullstack":
            return self.fullstack_generator.generate(prompt, task=task)
        raise ValueError("unsupported_target")

    def _choose_target_file(self, workspace: Path, prompt: str) -> Path:
        prompt_lower = prompt.lower()
        if any(marker in prompt_lower for marker in ("readme", "docs", "文档")):
            readme = workspace / "README.md"
            if readme.exists():
                return readme

        found = self.search_tool.search_files(workspace, "todo", max_results=1)
        if found:
            return found[0]

        candidates = sorted(
            p
            for p in workspace.rglob("*")
            if p.is_file() and p.suffix.lower() in {".md", ".txt", ".py", ".java", ".kt", ".js", ".ts"}
        )
        if candidates:
            return candidates[0]

        fallback = workspace / "AGENT_PATCH_PREVIEW.md"
        if "readme" in prompt_lower:
            fallback = workspace / "README.md"
        return fallback

    def _propose_content(self, *, before: str, prompt: str, task: dict[str, Any], target_file: Path) -> str:
        if self._should_use_llm_for_edit(prompt=prompt, task=task, target_file=target_file):
            try:
                return self.circuit_breaker.call(
                    lambda: self._edit_with_llm(before=before, prompt=prompt, task=task, target_file=target_file)
                )
            except Exception:
                pass
        note = f"\n# coder-agent-note: {prompt.strip() or 'applied structured update'}\n"
        if before.endswith("\n"):
            return before + note.lstrip("\n")
        return before + note

    def _edit_with_llm(self, *, before: str, prompt: str, task: dict[str, Any], target_file: Path) -> str:
        workspace = self._resolve_workspace(task)
        relative_path = self._relative_path(target_file, workspace)
        last_test_error = str(task.get("lastTestError", "")).strip()
        fix_attempt = int(task.get("fixLoopAttempt") or 0)
        observation = ensure_task_observability(task, engine=str(task.get("_agentEngine", "")).strip())
        cache_cursor = self.llm_client.cache_event_cursor()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a coding assistant editing exactly one file. "
                    "Return the full updated file content only. "
                    "Do not wrap the answer in markdown fences."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Task:\n{prompt.strip()}\n\n"
                    f"Target file:\n{relative_path}\n\n"
                    f"Fix loop attempt: {fix_attempt}\n"
                    f"Last test error: {last_test_error or 'n/a'}\n\n"
                    "Current file content:\n"
                    f"{before}"
                ),
            },
        ]
        try:
            raw = self.llm_client.chat(messages)
        finally:
            self.llm_client.record_cache_metrics(
                observation,
                stage="CoderAgent",
                backend=self.llm_client.settings.backend,
                since_sequence=cache_cursor,
            )
        text = str(raw or "").strip()
        if not text:
            raise ValueError("empty coder llm response")
        return text if text.endswith("\n") else f"{text}\n"

    def _resolve_target_files(self, task: dict[str, Any], plan) -> list:
        from pathlib import Path
        if self.code_index and self.code_index._files:
            prompt = str(task.get("prompt", ""))
            context = self.code_index.to_context_summary()
            user_msg = (
                f"Project structure:\n{context}\n\n"
                f"Task: {prompt}\n\n"
                f"List the files that need to be modified, one per line. Only list files that exist."
            )
            try:
                response = self.llm_client.generate(user_msg, system_prompt="You are a code navigation assistant. List only file paths.")
                files = [Path(line.strip()) for line in response.strip().split("\n") if line.strip() and not line.startswith("#")]
                return [f for f in files if (self.code_index.workspace / f).exists()]
            except Exception:
                pass
        target = self._choose_target_file(task, plan)
        return [target] if target else []

    def _apply_incremental_edit(self, file_path, prompt: str, workspace) -> str:
        from pathlib import Path
        full_path = Path(workspace) / file_path
        existing_content = ""
        if full_path.exists():
            existing_content = full_path.read_text(encoding="utf-8", errors="replace")
        context_summary = ""
        if self.code_index:
            context_summary = self.code_index.to_context_summary(max_files=20)
        user_msg = (
            f"File: {file_path}\n"
            f"Existing content:\n```\n{existing_content[:4000]}\n```\n\n"
            f"Project context:\n{context_summary[:2000]}\n\n"
            f"Modification request: {prompt}\n\n"
            f"Return the COMPLETE modified file content. No explanations."
        )
        return self.llm_client.generate(
            user_msg,
            system_prompt="You are a precise code editor. Return only the file content."
        )

    @staticmethod
    def _should_use_llm_for_edit(*, prompt: str, task: dict[str, Any], target_file: Path) -> bool:
        if int(task.get("fixLoopAttempt") or 0) > 0:
            return True
        text = (prompt or "").strip().lower()
        extension = target_file.suffix.lower()
        if extension in {".py", ".java", ".kt", ".js", ".ts"}:
            framework_markers = (
                "flask",
                "fastapi",
                "spring",
                "endpoint",
                "route",
                "api",
                "controller",
                "service",
                "health",
                "接口",
                "/health",
            )
            return any(marker in text for marker in framework_markers)
        return False

    @staticmethod
    def _resolve_workspace(task: dict[str, Any]) -> Path:
        workspace = CoderAgent._sanitize_workspace_value(task.get("workspacePath"))
        if not workspace:
            allowed = os.getenv("MVP_ALLOWED_WORKSPACE_PREFIXES", "").strip()
            for raw_prefix in allowed.split(","):
                sanitized = CoderAgent._sanitize_workspace_value(raw_prefix)
                if sanitized:
                    workspace = sanitized
                    break
        if not workspace:
            workspace = "."
        return Path(workspace).resolve(strict=False)

    @staticmethod
    def _sanitize_workspace_value(raw: Any) -> str:
        if raw is None:
            return ""
        text = str(raw).strip().strip('"').strip("'")
        if not text:
            return ""
        if text.lower() in {"none", "null", "undefined", "nil", "nan"}:
            return ""
        return text

    @staticmethod
    def _relative_path(target: Path, workspace: Path) -> str:
        try:
            relative = target.relative_to(workspace)
        except ValueError:
            relative = target.name
        return str(relative).replace("\\", "/")


class EventPublisher:
    def __call__(self, payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        raise NotImplementedError
