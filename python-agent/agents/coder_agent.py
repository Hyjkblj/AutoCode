from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.planner_agent import PlanResult
from client.control_plane_client import ControlPlaneClient
from llm.llm_client import LLMClient
from tools.file_tool import FileTool
from tools.search_tool import SearchTool
from utils.diff_utils import generate_unified_diff, has_substantial_change


class CoderAgent:
    def __init__(
        self,
        file_tool: FileTool | None = None,
        search_tool: SearchTool | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.file_tool = file_tool or FileTool()
        self.search_tool = search_tool or SearchTool()
        self.llm_client = llm_client or LLMClient()

    def execute(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publish_event: EventPublisher,
    ) -> bool:
        workspace = self._resolve_workspace(task)
        prompt = str(task.get("prompt", "")).strip()
        target_files = self._resolve_target_files(task, workspace, prompt)

        modified_count = 0
        generated_diffs: list[str] = []

        for target in target_files:
            relative = self._relative_path(target, workspace)
            try:
                existed_before = target.exists()
                before = self.file_tool.read_text(target) if existed_before else ""
                after = self._propose_content(
                    before=before,
                    prompt=prompt,
                    relative_path=relative,
                )
                patch = generate_unified_diff(before, after, relative)
                if not has_substantial_change(patch):
                    publish_event(
                        {
                            "stage": "CoderAgent",
                            "message": "No substantial change detected, skip write.",
                            "file": relative,
                            "planName": plan.plan_name,
                        }
                    )
                    continue

                self.file_tool.write_text(target, after)
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
                generated_diffs.append(patch)
                modified_count += 1
            except PermissionError as exc:
                publish_event(
                    {
                        "stage": "CoderAgent",
                        "message": "Write blocked by workspace allowlist.",
                        "file": relative,
                        "error": str(exc),
                    },
                )
                publish_event(
                    {
                        "reason": "path_not_allowed",
                        "detail": str(exc),
                        "file": relative,
                    },
                    event_type="TASK_FAILED",
                )
                continue
            except Exception as exc:  # noqa: BLE001
                publish_event(
                    {
                        "stage": "CoderAgent",
                        "message": "Failed to prepare code change.",
                        "file": relative,
                        "error": str(exc),
                    },
                )
                continue

        task["generatedDiffs"] = generated_diffs
        task["latestDiff"] = generated_diffs[-1] if generated_diffs else ""
        return modified_count > 0

    def _resolve_target_files(self, task: dict[str, Any], workspace: Path, prompt: str) -> list[Path]:
        raw_targets = task.get("target_files")
        if raw_targets is None:
            raw_targets = task.get("targetFiles")

        parsed: list[Path] = []
        if isinstance(raw_targets, (list, tuple)):
            for item in raw_targets:
                if not isinstance(item, str):
                    continue
                candidate = item.strip()
                if not candidate:
                    continue
                parsed.append(self._resolve_target_path(candidate, workspace))
        elif isinstance(raw_targets, str) and raw_targets.strip():
            for segment in raw_targets.split(","):
                candidate = segment.strip()
                if candidate:
                    parsed.append(self._resolve_target_path(candidate, workspace))

        if parsed:
            return _dedupe_paths(parsed)
        return [self._choose_target_file(workspace, prompt)]

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
    def _resolve_target_path(path_value: str, workspace: Path) -> Path:
        path = Path(path_value).expanduser()
        if not path.is_absolute():
            path = workspace / path
        return path.resolve(strict=False)

    def _propose_content(self, *, before: str, prompt: str, relative_path: str) -> str:
        if not self.llm_client.has_required_key():
            return self._fallback_content(before, prompt)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a coding assistant. Return ONLY the full updated file content. "
                    "Do not wrap output in markdown fences."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Task prompt:\n{prompt}\n\n"
                    f"Target file:\n{relative_path}\n\n"
                    f"Current file content:\n{before}"
                ),
            },
        ]
        try:
            candidate = self.llm_client.chat(messages)
        except Exception:
            return self._fallback_content(before, prompt)
        return candidate if candidate.strip() else self._fallback_content(before, prompt)

    @staticmethod
    def _fallback_content(original: str, prompt: str) -> str:
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


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


class EventPublisher:
    def __call__(self, payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        raise NotImplementedError
