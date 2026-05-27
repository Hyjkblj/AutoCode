from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from memory.knowledge_extractor import KnowledgeExtractor

class TestKnowledgeExtractor:
    def test_extract_file_summary(self):
        llm = MagicMock()
        llm.generate.return_value = "This file implements an ArticleService class."
        ke = KnowledgeExtractor(llm_client=llm)
        summary = ke.extract_file_summary("src/agent.ts", "export class ArticleService { getArticle() {} }")
        assert "ArticleService" in summary

    def test_extract_project_architecture(self):
        llm = MagicMock()
        llm.generate.return_value = '{"architecture": "React+Redux", "modules": ["auth", "articles"]}'
        ke = KnowledgeExtractor(llm_client=llm)
        idx = MagicMock()
        idx.to_context_summary.return_value = "agent.ts [typescript]\n  exports: ArticleService"
        result = ke.extract_project_architecture(idx)
        assert "architecture" in result

    def test_extract_no_llm(self):
        ke = KnowledgeExtractor(llm_client=None)
        assert ke.extract_file_summary("test.ts", "const x = 1;") == ""
        assert ke.extract_project_architecture(MagicMock()) == {}
