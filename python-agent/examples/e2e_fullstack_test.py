"""
End-to-end test: simulate a real mobile client request through the CoderAgent pipeline.
Bypasses the Java control plane - directly invokes CoderAgent with FullstackGenerator.

Usage:
    python examples/e2e_fullstack_test.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Ensure python-agent is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set workspace allowlist BEFORE importing anything
_workspace = Path(__file__).resolve().parent.parent.parent / "workspace"
os.environ["MVP_ALLOWED_WORKSPACE_PREFIXES"] = str(_workspace)

from agents.coder_agent import CoderAgent
from agents.planner_agent import PlanResult
from llm.llm_client import LLMClient


class FakeControlPlaneClient:
    """Stub that accepts publish_event calls without a real server."""
    def publish_event(self, *args, **kwargs):
        pass


def publish_event(payload: dict, event_type: str = "ASSISTANT_OUTPUT"):
    """Print events to stdout for monitoring."""
    stage = payload.get("stage", "")
    message = payload.get("message", "")
    if stage or message:
        print(f"  [{event_type}] {stage}: {message}")
    if "files" in payload:
        for f in payload["files"]:
            print(f"    -> {f.get('changeType', '?')} {f.get('path', '?')}")


def main():
    prompt = "做一个前后端分离的图书管理系统，包含图书CRUD、用户管理、借阅管理，后端Flask+SQLite，前端HTML/CSS/JS"

    workspace = Path(__file__).resolve().parent.parent.parent / "workspace" / "library-system-e2e"
    workspace.mkdir(parents=True, exist_ok=True)

    print(f"Prompt: {prompt}")
    print(f"Workspace: {workspace}")
    print(f"LLM: {LLMClient().settings.model}")
    print()

    task = {
        "taskId": "e2e-test-001",
        "prompt": prompt,
        "assistant": "fullstack",
        "target": "fullstack",
        "workspacePath": str(workspace),
    }

    plan = PlanResult(
        plan_name="library-management-system",
        steps=["Generate backend API", "Generate frontend UI", "Integrate"],
    )

    coder = CoderAgent()
    print("Running CoderAgent.execute()...")
    start = time.time()

    ok = coder.execute(
        task=task,
        client=FakeControlPlaneClient(),
        plan=plan,
        publish_event=publish_event,
    )

    elapsed = time.time() - start
    print()
    print(f"Result: {'SUCCESS' if ok else 'FAILED'} ({elapsed:.1f}s)")
    print(f"Generated target: {task.get('_generated_target', 'N/A')}")
    print(f"Fallback used: {task.get('_llm_fallback', 'N/A')}")
    print(f"Reason: {task.get('_llm_generation_reason', 'N/A')}")
    print()

    # List generated files
    print("=== Generated Files ===")
    for f in sorted(workspace.rglob("*")):
        if f.is_file():
            rel = f.relative_to(workspace)
            size = f.stat().st_size
            print(f"  {rel} ({size} bytes)")

    # Verify key files exist and are not templates
    app_py = workspace / "backend" / "app.py"
    if app_py.exists():
        content = app_py.read_text(encoding="utf-8", errors="replace")
        has_books = "book" in content.lower()
        has_users = "user" in content.lower()
        has_borrows = "borrow" in content.lower()
        is_template = "from models import PRIMARY_FIELD" in content and len(content) < 3000
        print()
        print("=== Verification ===")
        print(f"  app.py size: {len(content)} chars")
        print(f"  Has books: {has_books}")
        print(f"  Has users: {has_users}")
        print(f"  Has borrows: {has_borrows}")
        print(f"  Is template: {is_template}")
        if has_books and has_users and has_borrows and not is_template:
            print("  VERDICT: Custom LLM-generated code with all 3 tables!")
        else:
            print("  VERDICT: Template or incomplete generation")

    index_html = workspace / "frontend" / "index.html"
    if index_html.exists():
        content = index_html.read_text(encoding="utf-8", errors="replace")
        print(f"  index.html size: {len(content)} chars")
        has_resource_ui = any(kw in content.lower() for kw in ["book", "图书", "library"])
        print(f"  Has resource-specific UI: {has_resource_ui}")


if __name__ == "__main__":
    main()
