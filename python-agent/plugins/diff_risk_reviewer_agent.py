from __future__ import annotations

from agents.reviewer_agent import ReviewResult
from plugins.contracts import PluginContext


class DiffRiskReviewerAgent:
    manifest = None

    def supports(self, context: PluginContext) -> bool:
        diff_text = str(context.task.get("latestDiff") or context.task.get("diff") or context.task.get("patch") or "")
        return bool(diff_text.strip())

    def review(self, context: PluginContext) -> ReviewResult:
        diff_text = str(context.task.get("latestDiff") or context.task.get("diff") or context.task.get("patch") or "")
        lowered = diff_text.lower()
        issues: list[str] = []
        risk_level = "low"

        if any(token in lowered for token in ("rm -rf", "drop table", "truncate table", "chmod 777")):
            issues.append("dangerous_diff_tokens")
            risk_level = "high"
        elif any(token in lowered for token in ("subprocess", "os.system", "eval(", "exec(")):
            issues.append("runtime_execution_risk")
            risk_level = "medium"

        approved = risk_level != "high"
        summary = (
            "Plugin reviewer blocked dangerous diff."
            if risk_level == "high"
            else "Plugin reviewer completed risk scan."
        )
        result = ReviewResult(
            approved=approved,
            summary=summary,
            issues=issues,
            risk_level=risk_level,
        )
        context.publish_event(
            {
                "stage": "ReviewerPlugin",
                "message": "Plugin reviewer completed.",
                "pluginId": context.task.get("_activeReviewerPlugin"),
                "approved": result.approved,
                "summary": result.summary,
                "riskLevel": result.risk_level,
                "issues": result.issues,
            }
        )
        return result
