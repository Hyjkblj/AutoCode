from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.planner_agent import PlanResult
from client.control_plane_client import ControlPlaneClient
from llm.llm_client import LLMClient
from tools.search_tool import SearchTool
from utils.circuit_breaker import CircuitBreaker


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
_RISK_LEVELS = {"high", "medium", "low"}


@dataclass(frozen=True)
class ReviewResult:
    approved: bool
    summary: str
    issues: list[str]
    risk_level: str = "low"


class ReviewerAgent:
    def __init__(
        self,
        search_tool: SearchTool | None = None,
        llm_client: LLMClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.search_tool = search_tool or SearchTool()
        self.llm_client = llm_client or LLMClient()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(name="reviewer-llm")

    def review(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publish_event: EventPublisher,
    ) -> ReviewResult:
        workspace = _resolve_workspace(task)
        diff_text = _resolve_diff_text(task)
        if not diff_text.strip():
            result = ReviewResult(
                approved=True,
                summary="No diff provided, review accepted by default.",
                issues=[],
                risk_level="low",
            )
            publish_event(_review_payload(plan, result))
            return result

        if self.llm_client.has_required_key():
            try:
                llm_result = self._review_with_llm(diff_text)
                publish_event(_review_payload(plan, llm_result))
                return llm_result
            except Exception:
                pass

        blocker_files = self.search_tool.search_files(workspace, "REVIEW_BLOCKER", max_results=5)
        blockers = [_relative_path(path, workspace) for path in blocker_files]
        approved = not blockers
        risk_level = "high" if blockers else "low"
        summary = (
            "Review blocked by REVIEW_BLOCKER marker."
            if blockers
            else "LLM unavailable; fallback review passed with no blockers."
        )
        result = ReviewResult(approved=approved, summary=summary, issues=blockers, risk_level=risk_level)
        publish_event(_review_payload(plan, result))
        return result

    def _review_with_llm(self, diff_text: str) -> ReviewResult:
        messages = [
            {
                "role": "system",
                "content": (
                "You are a code reviewer. Return strict JSON with keys: risk_level, issues, summary. "
                "risk_level must be one of high, medium, low. issues must be a list of strings."
            ),
        },
            {
                "role": "user",
                "content": f"Review this unified diff:\n{diff_text}",
            },
        ]
        raw = self.circuit_breaker.call(lambda: self.llm_client.chat(messages))
        payload = _parse_json_object(raw)
        risk_level = _normalize_risk_level(payload.get("risk_level"))
        issues = _normalize_issues(payload.get("issues"))
        summary = str(payload.get("summary") or "LLM review completed.").strip() or "LLM review completed."
        approved = risk_level != "high"
        return ReviewResult(
            approved=approved,
            summary=summary,
            issues=issues,
            risk_level=risk_level,
        )


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


def _resolve_diff_text(task: dict[str, Any]) -> str:
    direct = task.get("latestDiff")
    if isinstance(direct, str) and direct.strip():
        return direct
    for key in ("diff", "patch"):
        value = task.get(key)
        if isinstance(value, str) and value.strip():
            return value
    for key in ("generatedDiffs", "diffs"):
        value = task.get(key)
        if isinstance(value, list):
            parts = [str(item).strip() for item in value if str(item).strip()]
            if parts:
                return "\n\n".join(parts)
    return ""


def _parse_json_object(raw: str) -> dict[str, object]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty reviewer response")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(text)
        if match is None:
            raise ValueError(f"reviewer response is not valid JSON: {text}") from None
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError(f"reviewer response must be an object: {payload!r}")
    return payload


def _normalize_risk_level(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _RISK_LEVELS:
        return normalized
    return "medium"


def _normalize_issues(value: object) -> list[str]:
    if isinstance(value, list):
        issues = [str(item).strip() for item in value if str(item).strip()]
        return issues
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _review_payload(plan: PlanResult, result: ReviewResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stage": "ReviewerAgent",
        "message": "Code review completed.",
        "planName": plan.plan_name,
        "approved": result.approved,
        "summary": result.summary,
        "riskLevel": result.risk_level,
        "issues": result.issues,
    }
    return payload
