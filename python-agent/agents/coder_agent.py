from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agents.planner_agent import PlanResult
from client.control_plane_client import ControlPlaneClient
from llm.llm_client import LLMClient
from tools.file_tool import FileTool
from tools.search_tool import SearchTool
from utils.diff_utils import generate_unified_diff, has_substantial_change
from utils.web_template import WebTemplateGenerator


class CoderAgent:
    def __init__(
        self,
        file_tool: FileTool | None = None,
        search_tool: SearchTool | None = None,
        llm_client: LLMClient | None = None,
        web_template_generator: WebTemplateGenerator | None = None,
    ) -> None:
        self.file_tool = file_tool or FileTool()
        self.search_tool = search_tool or SearchTool()
        self.llm_client = llm_client or LLMClient()
        self.web_template_generator = web_template_generator or WebTemplateGenerator(llm_client=self.llm_client)

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
        if target == "web":
            return self._generate_web_project(task, plan, publish_event, workspace, prompt)

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
                        "errorCode": _error_code_from_reason("path_not_allowed"),
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

    def _generate_web_project(
        self,
        task: dict[str, Any],
        plan: PlanResult,
        publish_event: EventPublisher,
        workspace: Path,
        prompt: str,
    ) -> bool:
        template = self.web_template_generator.generate(prompt, target="web")
        generated_diffs: list[str] = []
        generated_files: list[str] = []
        modified_count = 0

        for relative, content in template.files.items():
            target_path = self._resolve_target_path(relative, workspace)
            try:
                existed_before = target_path.exists()
                before = self.file_tool.read_text(target_path) if existed_before else ""
                patch = generate_unified_diff(before, content, relative)
                if not has_substantial_change(patch):
                    continue
                self.file_tool.write_text(target_path, content)
                publish_event(
                    {
                        "format": "unified",
                        "patch": patch,
                        "files": [{"path": relative, "changeType": "modify" if existed_before else "add"}],
                    },
                    event_type="FILE_PATCH_PREVIEW",
                )
                generated_diffs.append(patch)
                generated_files.append(relative)
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
                        "errorCode": _error_code_from_reason("path_not_allowed"),
                        "detail": str(exc),
                        "file": relative,
                    },
                    event_type="TASK_FAILED",
                )
                continue

        task["_generated_files"] = generated_files if generated_files else list(template.files.keys())
        task["_llm_fallback"] = bool(template.used_fallback)
        task["_llm_generation_reason"] = template.reason
        task["generatedDiffs"] = generated_diffs
        task["latestDiff"] = generated_diffs[-1] if generated_diffs else ""

        publish_event(
            {
                "stage": "CoderAgent",
                "message": "Web template generated.",
                "planName": plan.plan_name,
                "target": "web",
                "fileCount": len(task["_generated_files"]),
                "fallbackUsed": task["_llm_fallback"],
                "reason": task["_llm_generation_reason"],
            },
        )
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


def _error_code_from_reason(reason: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(reason).strip()).strip("_")
    if not normalized:
        return "UNKNOWN_ERROR"
    return normalized.upper()
