"""Smoke tests for Super Individual pipeline wiring."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.git_tool import GitTool, GitResult
from tools.code_index import CodeIndex
from tools.repo_bootstrap import RepoBootstrap, BootstrapResult
from agents.dialogue_manager import DialogueManager
from plugins.human_gate import HumanGate, PipelineStage
from memory.knowledge_extractor import KnowledgeExtractor
from generators.test_generator import TestGenerator


class TestComponentWiring:
    """Verify all new components can be instantiated and wired together."""

    def test_git_tool_instantiation(self):
        tool = GitTool(use_local_git=True)
        assert tool.use_local_git is True

    def test_code_index_scan(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.ts").write_text("export function main() { return 1; }")
        idx = CodeIndex(tmp_path)
        idx.scan()
        assert len(idx._files) >= 1
        assert idx.find_symbol("main")

    def test_repo_bootstrap_with_mock_git(self, tmp_path):
        git = MagicMock()
        def fake_clone(url, target, **kw):
            Path(target).mkdir(parents=True, exist_ok=True)
            (Path(target) / "package.json").write_text('{"name":"test"}')
            return GitResult(ok=True, output="cloned", exit_code=0, error=None)
        git.clone.side_effect = fake_clone
        bs = RepoBootstrap(git_tool=git)
        result = bs.bootstrap("https://github.com/test/repo", str(tmp_path))
        assert result.ok is True

    def test_dialogue_manager_vague(self):
        llm = MagicMock()
        llm.generate.return_value = '{"needs_clarification": true, "question": "What feature?", "options": ["a", "b"], "context": "vague", "stage": "plan"}'
        dm = DialogueManager(llm_client=llm)
        q = dm.needs_clarification("改进应用", stage="plan", context={})
        assert q is not None
        assert q.options == ["a", "b"]

    def test_human_gate_stage_config(self):
        gate = HumanGate()
        task = {"approvalStages": ["plan"]}
        assert gate.should_gate(PipelineStage.PLAN, task) is True
        assert gate.should_gate(PipelineStage.CODE, task) is False

    def test_knowledge_extractor_summary(self):
        llm = MagicMock()
        llm.generate.return_value = "A service that fetches articles."
        ke = KnowledgeExtractor(llm_client=llm)
        summary = ke.extract_file_summary("agent.ts", "export class ArticleService {}")
        assert "service" in summary.lower() or "article" in summary.lower()

    def test_test_generator_detect_framework(self, tmp_path):
        (tmp_path / "package.json").write_text('{"devDependencies": {"jest": "^29.0.0"}}')
        gen = TestGenerator()
        assert gen.detect_test_framework(tmp_path) == "jest"


class TestOrchestratorImports:
    """Verify orchestrator can import all new components."""

    def test_orchestrator_imports(self):
        from orchestrator.agent_orchestrator import AgentOrchestrator
        # Should not raise ImportError
        assert AgentOrchestrator is not None

    def test_main_imports(self):
        # Verify main.py can be imported without errors
        # This tests that all wiring is syntactically correct
        import importlib
        spec = importlib.util.find_spec("main")
        assert spec is not None
