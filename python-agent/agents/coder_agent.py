from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from agents.planner_agent import PlanResult
from client.control_plane_client import ControlPlaneClient
from tools.file_tool import FileTool
from tools.search_tool import SearchTool


class CoderAgent:
    def __init__(self, file_tool: FileTool | None = None, search_tool: SearchTool | None = None) -> None:
        self.file_tool = file_tool or FileTool()
        self.search_tool = search_tool or SearchTool()

    def execute(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publish_event: EventPublisher,
    ) -> bool:
        workspace = self._resolve_workspace(task)
        prompt = str(task.get("prompt", "")).strip()

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
        workspace = str(task.get("workspacePath", "")).strip()
        if not workspace:
            workspace = "."
        return Path(workspace).resolve(strict=False)

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
