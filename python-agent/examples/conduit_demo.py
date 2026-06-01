"""
Demo script showing the Super Individual pipeline in action.

Usage:
    python conduit_demo.py

This script demonstrates the pipeline components without requiring
a live Conduit repository or LLM API key. It uses mocks to show
the flow.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.git_tool import GitTool, GitResult
from tools.code_index import CodeIndex
from tools.repo_bootstrap import RepoBootstrap
from agents.dialogue_manager import DialogueManager
from plugins.human_gate import HumanGate, PipelineStage
from memory.knowledge_extractor import KnowledgeExtractor
from generators.test_generator import TestGenerator


def demo_code_index():
    """Demo: Index a TypeScript project."""
    print("\n=== CodeIndex Demo ===")
    # Create a sample project
    demo_dir = Path(__file__).parent / "demo_project"
    demo_dir.mkdir(exist_ok=True)
    src = demo_dir / "src"
    src.mkdir(exist_ok=True)

    (src / "ArticleList.tsx").write_text("""
import React from 'react';
import { Article } from './types';

export function ArticleList({ articles }: { articles: Article[] }) {
    return (
        <div>
            {articles.map(a => <ArticleCard key={a.slug} article={a} />)}
        </div>
    );
}

export default ArticleList;
""".strip())

    (src / "types.ts").write_text("""
export interface Article {
    slug: string;
    title: string;
    body: string;
    favoritesCount: number;
}
""".strip())

    idx = CodeIndex(demo_dir)
    idx.scan()

    print(f"Files indexed: {len(idx._files)}")
    for path, info in idx._files.items():
        print(f"  {path} [{info.language}]: {len(info.symbols)} symbols")
        for sym in info.symbols:
            print(f"    {sym.kind}: {sym.name} (line {sym.line})")

    print(f"\nContext summary:\n{idx.to_context_summary()}")
    return demo_dir


def demo_dialogue_manager():
    """Demo: Requirement clarification."""
    print("\n=== DialogueManager Demo ===")
    llm = MagicMock()
    llm.generate.return_value = '''{"needs_clarification": true, "question": "What specific feature would you like to add to the article list?", "options": ["Pagination", "Search", "Sorting", "Favorites badge"], "context": "The request is broad", "stage": "plan"}'''

    dm = DialogueManager(llm_client=llm)
    q = dm.needs_clarification("改进文章列表", stage="plan", context={})
    if q:
        print(f"Question: {q.question}")
        print(f"Options: {q.options}")
        merged = dm.incorporate_clarification("改进文章列表", "加分页功能")
        print(f"Merged prompt: {merged}")


def demo_human_gate():
    """Demo: Pipeline stage gating."""
    print("\n=== HumanGate Demo ===")
    gate = HumanGate()
    task = {"approvalStages": ["plan", "code"]}

    for stage in PipelineStage:
        should_gate = gate.should_gate(stage, task)
        print(f"  {stage.value}: {'GATED' if should_gate else 'PASS'}")


def demo_knowledge():
    """Demo: Knowledge extraction."""
    print("\n=== KnowledgeExtractor Demo ===")
    llm = MagicMock()
    llm.generate.return_value = "ArticleList component renders a list of articles with React. Depends on Article type from types.ts."

    ke = KnowledgeExtractor(llm_client=llm)
    summary = ke.extract_file_summary("src/ArticleList.tsx", "export function ArticleList() {}")
    print(f"File summary: {summary}")


if __name__ == "__main__":
    print("Super Individual Pipeline Demo")
    print("=" * 40)

    demo_dir = demo_code_index()
    demo_dialogue_manager()
    demo_human_gate()
    demo_knowledge()

    print("\n" + "=" * 40)
    print("Demo complete!")

    # Cleanup
    import shutil
    shutil.rmtree(demo_dir, ignore_errors=True)
