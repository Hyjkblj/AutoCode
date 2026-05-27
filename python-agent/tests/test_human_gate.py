from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from plugins.human_gate import GateDecision, HumanGate, PipelineStage

class TestPipelineStage:
    def test_stages_exist(self):
        assert PipelineStage.PLAN.value == "plan"
        assert PipelineStage.CODE.value == "code"
        assert PipelineStage.TEST.value == "test"
        assert PipelineStage.DEPLOY.value == "deploy"

class TestHumanGate:
    def test_should_gate_when_configured(self):
        gate = HumanGate()
        task = {"approvalStages": ["plan", "code"]}
        assert gate.should_gate(PipelineStage.PLAN, task) is True
        assert gate.should_gate(PipelineStage.CODE, task) is True
        assert gate.should_gate(PipelineStage.TEST, task) is False

    def test_should_gate_default_none(self):
        gate = HumanGate()
        assert gate.should_gate(PipelineStage.PLAN, {}) is False

    def test_request_approval(self):
        gate = HumanGate(client=MagicMock())
        task = {"taskId": "t1", "assistant": "ai"}
        approval_id = gate.request_approval(task, PipelineStage.PLAN, "Plan summary", {"steps": ["a"]})
        assert isinstance(approval_id, str)
        assert len(approval_id) > 0

    def test_check_approval_unknown(self):
        gate = HumanGate()
        decision = gate.check_approval("nonexistent")
        assert decision.approved is False

    def test_check_approval_auto_approve(self):
        gate = HumanGate(client=None)
        aid = gate.request_approval({}, PipelineStage.PLAN, "s", {})
        decision = gate.check_approval(aid)
        assert decision.approved is True
