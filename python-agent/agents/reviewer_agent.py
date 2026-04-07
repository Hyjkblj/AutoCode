from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.planner_agent import PlanResult
from client.control_plane_client import ControlPlaneClient
from tools.search_tool import SearchTool


@dataclass(frozen=True)
class ReviewResult:
    approved: bool
    summary: str
    issues: list[str]


class ReviewerAgent:
    def __init__(self, search_tool: SearchTool | None = None) -> None:
        self.search_tool = search_tool or SearchTool()

    def review(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publish_event: EventPublisher,
    ) -> ReviewResult:
        workspace = _resolve_workspace(task)
        blocker_files = self.search_tool.search_files(workspace, "REVIEW_BLOCKER", max_results=5)
        blockers = [_relative_path(path, workspace) for path in blocker_files]

        approved = not blockers
        summary = "Review passed with no blockers." if approved else "Review blocked by REVIEW_BLOCKER marker."

        payload: dict[str, Any] = {
            "stage": "ReviewerAgent",
            "message": "Code review completed.",
            "planName": plan.plan_name,
            "approved": approved,
            "summary": summary,
        }
        if blockers:
            payload["issues"] = blockers
        publish_event(payload)

        return ReviewResult(approved=approved, summary=summary, issues=blockers)


class EventPublisher:
    def __call__(self, payload: dict[str, Any], event_type: str = "ASSISTANT_OUTPUT") -> None:
        raise NotImplementedError


def _resolve_workspace(task: dict[str, Any]) -> Path:
    workspace = str(task.get("workspacePath", "")).strip()
    if not workspace:
        workspace = "."
    return Path(workspace).resolve(strict=False)


def _relative_path(path: Path, workspace: Path) -> str:
    try:
        relative = path.relative_to(workspace)
    except ValueError:
        relative = path.name
    return str(relative).replace("\\", "/")

