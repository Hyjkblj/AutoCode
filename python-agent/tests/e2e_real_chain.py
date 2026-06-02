"""
真实业务链路端到端验证脚本（不依赖 MySQL/Redis/控制面）

验证场景：
  S1 · target=web + 具体 prompt  →  产出 zip artifact（核心路径）
  S2 · llm_key_missing           →  TASK_FAILED，不假成功
  S3 · target=miniapp             →  TASK_FAILED(unsupported_target)，不静默
  S4 · 通用 prompt 无 target      →  关键词 fallback，走 web 生成
  S5 · "给 Flask app 增加 /health 接口" →  intent=code_change，不是 analyze
"""
from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import zipfile
from pathlib import Path
from typing import Any

# ── 把 python-agent 加入 sys.path ────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── 读取 .env（若存在）───────────────────────────────────────────────────────
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from agents.intent_agent import IntentAgent
from agents.coder_agent import CoderAgent
from agents.planner_agent import PlannerAgent
from agents.reviewer_agent import ReviewerAgent
from agents.tester_agent import TesterAgent
from agents.tester_agent import TesterResult
from orchestrator.agent_orchestrator import AgentOrchestrator
from client.control_plane_client import ControlPlaneClient
from utils.web_template import WebTemplateGenerator


# ─────────────────────────────── 辅助 ────────────────────────────────────────

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "-->"

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, detail))
    icon = PASS if cond else FAIL
    print(f"  {icon} {name}" + (f"  [{detail}]" if detail else ""))


class _StubClient:
    """控制面 stub：收集所有 publish_event 调用。"""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any]:
        self.events.append(event)
        return {}

    def upload_artifact(self, task_id: str, file_path: str, **_kw) -> dict[str, Any]:
        return {"artifactId": f"art_{task_id}", "name": "export.zip"}


class _AlwaysPassTester(TesterAgent):
    def execute(self, task, client, plan, publish_event):
        return TesterResult(
            success=True, attempts=1, retries=0,
            command="echo ok", status="ok",
            reason=None, trace_id="trc_e2e", run_id="run_e2e",
        )


def _run_task(prompt: str, extra: dict | None = None, workspace: Path | None = None) -> _StubClient:
    ws = workspace or Path(tempfile.mkdtemp())
    task: dict[str, Any] = {
        "taskId": "e2e_task_001",
        "sessionKey": "e2e_sess",
        "assistant": "web",
        "prompt": prompt,
        "workspacePath": str(ws),
    }
    if extra:
        task.update(extra)

    client = _StubClient()
    orch = AgentOrchestrator(tester_agent=_AlwaysPassTester())
    orch.handle_task(task, client)
    return client


def _event_types(client: _StubClient) -> list[str]:
    return [e["type"] for e in client.events]


def _last_reason(client: _StubClient) -> str:
    for e in reversed(client.events):
        if e.get("type") == "TASK_FAILED":
            return e.get("payload", {}).get("reason", "")
    return ""


# ─────────────────────────────── 场景 ────────────────────────────────────────

def s1_web_target_with_real_llm() -> None:
    """S1: target=web + 具体 prompt → 真实 LLM 生成 → ARTIFACT_READY + zip 可解包"""
    print(f"\n{INFO} S1: target=web + 真实 LLM 生成 artifact")
    with tempfile.TemporaryDirectory() as ws:
        ws_path = Path(ws)
        os.environ["MVP_ALLOWED_WORKSPACE_PREFIXES"] = ws
        client = _run_task(
            prompt="做一个番茄钟计时器页面，支持 25 分钟工作和 5 分钟休息",
            extra={"target": "web", "exportMode": "zip"},
            workspace=ws_path,
        )

    types = _event_types(client)
    print(f"    事件序列: {types}")

    check("S1-a 未触发 TASK_FAILED", "TASK_FAILED" not in types)
    check("S1-b 触发 ARTIFACT_READY", "ARTIFACT_READY" in types)

    # 找到 ARTIFACT_READY 事件，验证 zip 可解包
    art_event = next((e for e in client.events if e["type"] == "ARTIFACT_READY"), None)
    if art_event:
        zip_path = art_event.get("payload", {}).get("artifact", {}).get("localPath", "")
        if zip_path and Path(zip_path).exists():
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
            check("S1-c zip 包含 index.html", any("index.html" in n for n in names), str(names))
            check("S1-d zip 包含 styles.css",  any("styles.css"  in n for n in names))
            check("S1-e zip 包含 app.js",      any("app.js"      in n for n in names))
        else:
            # artifact 已在工作区，检查文件存在（upload_artifact 被 stub）
            check("S1-c ARTIFACT_READY 事件携带 artifactId",
                  bool(art_event.get("payload", {}).get("artifact", {}).get("artifactId")))
    else:
        check("S1-c ARTIFACT_READY event payload 存在", False, "event missing")


def s2_llm_key_missing() -> None:
    """S2: ANTHROPIC_API_KEY 缺失 + LLM_BACKEND=claude → TASK_FAILED(llm_key_missing)"""
    print(f"\n{INFO} S2: llm_key_missing → TASK_FAILED，不假成功")
    orig_backend = os.environ.get("LLM_BACKEND")
    orig_key = os.environ.get("ANTHROPIC_API_KEY")
    os.environ["LLM_BACKEND"] = "claude"
    os.environ.pop("ANTHROPIC_API_KEY", None)

    try:
        client = _run_task("分析这段代码")
    finally:
        if orig_backend is not None:
            os.environ["LLM_BACKEND"] = orig_backend
        if orig_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = orig_key

    types = _event_types(client)
    reason = _last_reason(client)
    print(f"    事件序列: {types}  reason={reason}")

    check("S2-a 最终事件是 TASK_FAILED", types[-1] == "TASK_FAILED", str(types))
    check("S2-b reason=llm_key_missing",  reason == "llm_key_missing", reason)
    check("S2-c 没有进入 PlannerAgent",
          not any(e.get("payload", {}).get("stage") == "PlannerAgent" for e in client.events))


def s3_unsupported_target() -> None:
    """S3: target=miniapp → TASK_FAILED(unsupported_target)，不静默走错路径"""
    print(f"\n{INFO} S3: target=miniapp → 明确 TASK_FAILED")
    client = _run_task("生成一个天气小程序", extra={"target": "miniapp"})
    types = _event_types(client)
    reason = _last_reason(client)
    print(f"    事件序列: {types}  reason={reason}")

    check("S3-a 最终事件是 TASK_FAILED", types[-1] == "TASK_FAILED", str(types))
    check("S3-b reason=unsupported_target", reason == "unsupported_target", reason)


def s4_keyword_fallback_no_target() -> None:
    """S4: 无 target，prompt 含网页关键词 → 关键词 fallback 触发 web 生成"""
    print(f"\n{INFO} S4: 无 target，prompt 含 '页面' → fallback 触发 web 生成")
    with tempfile.TemporaryDirectory() as ws:
        ws_path = Path(ws)
        os.environ["MVP_ALLOWED_WORKSPACE_PREFIXES"] = ws
        client = _run_task(
            prompt="做一个简单的天气查询页面",
            workspace=ws_path,
        )

    types = _event_types(client)
    print(f"    事件序列: {types}")
    check("S4-a 未触发 TASK_FAILED(unsupported_target)",
          _last_reason(client) != "unsupported_target")
    # 触发 web 路径：应有 FILE_PATCH_PREVIEW 或 ARTIFACT_READY
    check("S4-b 进入 web 生成路径",
          "ARTIFACT_READY" in types or "FILE_PATCH_PREVIEW" in types,
          str(types))


def s5_intent_flask_health() -> None:
    """S5: '给 Flask app 增加 /health 接口' → intent=code_change（不是 analyze）"""
    print(f"\n{INFO} S5: Flask /health prompt → intent=code_change")
    decision = IntentAgent().infer("给 Flask app 增加 /health 接口")
    print(f"    intent={decision.intent}  reason={decision.reason}  confidence={decision.confidence}")
    check("S5-a intent=code_change", decision.intent == "code_change", decision.intent)
    check("S5-b confidence > 0.5",   decision.confidence > 0.5, str(decision.confidence))


# ─────────────────────────────── 主入口 ──────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  端到端真实链路验证")
    print("=" * 60)

    s5_intent_flask_health()   # 纯规则，最快
    s2_llm_key_missing()       # 纯规则
    s3_unsupported_target()    # 纯规则

    llm_ok = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ARK_API_KEY"))
    if llm_ok:
        s4_keyword_fallback_no_target()  # 调用真实 LLM
        s1_web_target_with_real_llm()    # 调用真实 LLM（最慢）
    else:
        print(f"\n{INFO} S1/S4 跳过：未配置 LLM key（OPENAI_API_KEY / ARK_API_KEY）")

    # ── 汇总 ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"  结果: {passed} 通过 / {failed} 失败 / {len(results)} 总计")
    if failed:
        print(f"\n  失败项目:")
        for name, ok, detail in results:
            if not ok:
                print(f"    {FAIL} {name}  {detail}")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
