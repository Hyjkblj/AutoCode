from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agents.dialogue_manager import ClarificationQuestion, DialogueManager


class TestDialogueManager:
    @pytest.fixture
    def llm(self):
        return MagicMock()

    def test_vague_prompt_triggers_clarification(self, llm):
        llm.generate.return_value = '{"needs_clarification": true, "question": "What specific feature?", "options": ["pagination", "search", "sorting"], "context": "too vague", "stage": "plan"}'
        dm = DialogueManager(llm_client=llm)
        result = dm.needs_clarification("改进一下这个应用", stage="plan", context={})
        assert result is not None
        assert "What specific" in result.question
        assert len(result.options) == 3

    def test_specific_prompt_no_clarification(self, llm):
        llm.generate.return_value = '{"needs_clarification": false}'
        dm = DialogueManager(llm_client=llm)
        result = dm.needs_clarification("给文章列表中的每篇文章加一个收藏数徽章", stage="plan", context={})
        assert result is None

    def test_incorporate_clarification(self, llm):
        dm = DialogueManager(llm_client=llm)
        merged = dm.incorporate_clarification("改进应用", "加文章分页功能")
        assert "分页" in merged or "文章" in merged
        assert len(merged) > len("改进应用")

    def test_summarize_context_empty(self, llm):
        dm = DialogueManager(llm_client=llm)
        assert dm.summarize_context() == ""

    def test_summarize_context_with_turns(self, llm):
        dm = DialogueManager(llm_client=llm)
        dm._turns.append({"role": "user", "content": "加搜索功能"})
        dm._turns.append({"role": "assistant", "content": "请问搜索范围？"})
        dm._turns.append({"role": "user", "content": "全文搜索"})
        summary = dm.summarize_context(max_turns=10)
        assert "搜索" in summary
