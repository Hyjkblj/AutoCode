from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Any

from agents.planner_agent import PlanResult
from client.control_plane_client import ControlPlaneClient
from tools.file_tool import FileTool
from tools.search_tool import SearchTool
from utils.web_template import WebTemplateGenerator


class CoderAgent:
    def __init__(
        self,
        file_tool: FileTool | None = None,
        search_tool: SearchTool | None = None,
        web_template_generator: WebTemplateGenerator | None = None,
    ) -> None:
        self.file_tool = file_tool or FileTool()
        self.search_tool = search_tool or SearchTool()
        self.web_template_generator = web_template_generator or WebTemplateGenerator()

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

        if self._should_generate_project(target=target, assistant=assistant, prompt=prompt):
            return self._generate_web_project(task, plan, publish_event, workspace, prompt)

        try:
            target = self._choose_target_file(workspace, prompt)
            existed_before = target.exists()
            before = self.file_tool.read_text(target) if existed_before else ""
            after = self._propose_content(before, prompt)
            self.file_tool.write_text(target, after)
        except PermissionError as exc:
            publish_event(
                {
                    "stage": "CoderAgent",
                    "message": "Write blocked by workspace allowlist.",
                    "error": str(exc),
                },
            )
            publish_event({"reason": "path_not_allowed", "detail": str(exc)}, event_type="TASK_FAILED")
            return False
        except Exception as exc:  # noqa: BLE001
            publish_event(
                {
                    "stage": "CoderAgent",
                    "message": "Failed to prepare code change.",
                    "error": str(exc),
                },
            )
            publish_event({"reason": "coder_error", "detail": str(exc)}, event_type="TASK_FAILED")
            return False

        relative = self._relative_path(target, workspace)
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
            },
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
    def _should_generate_project(*, target: str, assistant: str, prompt: str) -> bool:
        normalized_target = (target or "").strip().lower()
        if normalized_target:
            return normalized_target == "web"

        normalized_assistant = (assistant or "").strip().lower()
        if normalized_assistant in {"web", "website"}:
            return True

        text = (prompt or "").strip().lower()
        if not text:
            return False

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
            "\u7f51\u9875",
            "\u9875\u9762",
            "\u4eea\u8868\u76d8",
            "\u8ba1\u7b97\u5668",
            "\u5f85\u529e",
            "\u5929\u6c14",
            "\u5c55\u793a",
            "\u8868\u5355",
            "\u7ba1\u7406\u7cfb\u7edf",
        )
        if any(marker in text for marker in strong_web_markers):
            return True

        action_markers = (
            "generate",
            "build",
            "create",
            "make",
            "\u751f\u6210",
            "\u642d\u5efa",
            "\u505a\u4e00\u4e2a",
            "\u505a\u4e2a",
        )
        weak_web_markers = ("web", "\u7f51\u7ad9", "\u5e94\u7528")
        return any(action in text for action in action_markers) and any(marker in text for marker in weak_web_markers)

    def _generate_web_project(
        self,
        task: dict[str, Any],
        plan: PlanResult,
        publish_event: EventPublisher,
        workspace: Path,
        prompt: str,
    ) -> bool:
        try:
            template = self.web_template_generator.generate(prompt, target="web")
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
                        "message": "Web template generation produced no file changes.",
                        "planName": plan.plan_name,
                        "fallbackUsed": template.used_fallback,
                        "reason": template.reason,
                    },
                )
                return True

            publish_event(
                {
                    "stage": "CoderAgent",
                    "message": "Web template generated.",
                    "planName": plan.plan_name,
                    "target": "web",
                    "fileCount": len(changed_files),
                    "fallbackUsed": template.used_fallback,
                    "reason": template.reason,
                },
            )
            return True
        except PermissionError as exc:
            publish_event(
                {
                    "stage": "CoderAgent",
                    "message": "Write blocked by workspace allowlist.",
                    "error": str(exc),
                },
            )
            publish_event({"reason": "path_not_allowed", "detail": str(exc)}, event_type="TASK_FAILED")
            return False
        except Exception as exc:  # noqa: BLE001
            publish_event(
                {
                    "stage": "CoderAgent",
                    "message": "Failed to generate web project.",
                    "error": str(exc),
                },
            )
            publish_event({"reason": "web_generation_failed", "detail": str(exc)}, event_type="TASK_FAILED")
            return False

    def _choose_target_file(self, workspace: Path, prompt: str) -> Path:
        prompt_lower = prompt.lower()
        found = self.search_tool.search_files(workspace, "todo", max_results=1)
        if found:
            return found[0]

        candidates = sorted(
            p
            for p in workspace.rglob("*")
            if p.is_file() and p.suffix.lower() in {".md", ".txt", ".py", ".java", ".kt"}
        )
        if candidates:
            return candidates[0]

        fallback = workspace / "AGENT_PATCH_PREVIEW.md"
        if "readme" in prompt_lower:
            fallback = workspace / "README.md"
        return fallback

    @staticmethod
    def _propose_content(original: str, prompt: str) -> str:
        note = f"\n# coder-agent-note: {prompt.strip() or 'applied structured update'}\n"
        if original.endswith("\n"):
            return original + note.lstrip("\n")
        return original + note

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
