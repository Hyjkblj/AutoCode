from __future__ import annotations

import os
from pathlib import Path

# Load .env from the same directory as this file (does not override existing env vars)
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

import argparse

from client.control_plane_client import ControlPlaneClient
from orchestrator.agent_orchestrator import AgentOrchestrator
from runner import AgentRunner, RunnerConfig


def _read_int_env(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _build_capabilities(profile: str) -> str:
    extra = os.getenv("MVP_AGENT_CAPABILITIES", "").strip()
    base = f"ai-agent,events,approval,profile:{profile}"
    if not extra:
        return base
    return f"{base},{extra}"


def _build_config() -> RunnerConfig:
    profile = os.getenv("MVP_AGENT_PROFILE", "ai-agent").strip() or "ai-agent"
    profile = profile.lower()
    return RunnerConfig(
        base_url=os.getenv("MVP_BASE_URL", "http://localhost:8058").strip() or "http://localhost:8058",
        node_id=os.getenv("MVP_NODE_ID", "ai-node-local-1").strip() or "ai-node-local-1",
        agent_token=os.getenv("MVP_AGENT_TOKEN", "agent-dev-token").strip() or "agent-dev-token",
        agent_profile=profile,
        poll_interval_ms=_read_int_env("MVP_POLL_INTERVAL_MS", 1500),
        heartbeat_interval_ms=_read_int_env("MVP_HEARTBEAT_INTERVAL_MS", 10000),
        agent_version=os.getenv("MVP_AGENT_VERSION", "0.1.0").strip() or "0.1.0",
        capabilities=_build_capabilities(profile),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="AutoCode Python AI Agent")
    parser.add_argument("--once", action="store_true", help="Run one poll tick then exit.")
    args = parser.parse_args()

    config = _build_config()
    client = ControlPlaneClient(
        base_url=config.base_url,
        agent_token=config.agent_token,
        agent_version=config.agent_version,
    )
    runner = AgentRunner(client=client, config=config, agent=AgentOrchestrator())
    if args.once:
        runner.tick()
        return 0
    runner.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
