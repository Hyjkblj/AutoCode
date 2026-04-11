from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from agents.base_agent import BaseAgent
from client.control_plane_client import ControlPlaneClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunnerConfig:
    base_url: str
    node_id: str
    agent_token: str
    agent_profile: str = "ai-agent"
    poll_interval_ms: int = 1500
    heartbeat_interval_ms: int = 10000
    agent_version: str = "0.1.0"
    capabilities: str = "ai-agent,events,approval,profile:ai-agent"


class AgentRunner:
    def __init__(self, client: ControlPlaneClient, config: RunnerConfig, agent: BaseAgent) -> None:
        self.client = client
        self.config = config
        self.agent = agent
        self._registered = False
        self._last_heartbeat_ms = 0

    def run_forever(self) -> None:
        log.info("Agent runner started, polling %s every %dms", self.config.base_url, self.config.poll_interval_ms)
        while True:
            try:
                handled = self.tick()
            except Exception as exc:  # noqa: BLE001
                log.warning("tick error (will retry): %s", exc)
                self._registered = False
                time.sleep(self.config.poll_interval_ms / 1000.0)
                continue
            if not handled:
                time.sleep(self.config.poll_interval_ms / 1000.0)

    def tick(self, now_ms: Optional[int] = None) -> bool:
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        self._ensure_registered(now)
        self._maybe_heartbeat(now)
        task = self.client.poll_next_task(self.config.node_id, profile=self.config.agent_profile)
        if not task:
            return False
        self.agent.handle_task(task, self.client)
        return True

    def _ensure_registered(self, now_ms: int) -> None:
        if self._registered:
            return
        self.client.register(self.config.node_id, capabilities=self.config.capabilities)
        self._registered = True
        self._last_heartbeat_ms = now_ms
        log.info("Registered node %s to %s", self.config.node_id, self.config.base_url)

    def _maybe_heartbeat(self, now_ms: int) -> None:
        if now_ms - self._last_heartbeat_ms < self.config.heartbeat_interval_ms:
            return
        self.client.heartbeat(self.config.node_id)
        self._last_heartbeat_ms = now_ms
        log.info("Heartbeat sent")

