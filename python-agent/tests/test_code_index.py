from __future__ import annotations

from pathlib import Path

import pytest

from tools.code_index import CodeIndex, FileInfo, SymbolInfo


@pytest.fixture
def sample_ts_project(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "agent.ts").write_text(
        """
import { Article } from './models/article';

const API_ROOT = 'https://conduit.productionready.io/api';

export function fetchArticles(): Promise<Article[]> {
    return fetch(`${API_ROOT}/articles`).then(res => res.json());
}

export class ArticleService {
    constructor(private root: string) {}
    getArticle(slug: string) {
        return fetch(`${this.root}/articles/${slug}`);
    }
}
""".strip()
    )

    models = src / "models"
    models.mkdir()
    (models / "article.ts").write_text(
        """
export interface Article {
    slug: string;
    title: string;
    body: string;
    description: string;
    tagList: string[];
    createdAt: string;
    updatedAt: string;
    favorited: boolean;
    favoritesCount: number;
}

export type ArticleList = Article[];
""".strip()
    )

    (src / "reducer.ts").write_text(
        """
import { Article } from './models/article';

export interface ArticleState {
    articles: Article[];
    loading: boolean;
}

export function articleReducer(state: ArticleState, action: any): ArticleState {
    switch (action.type) {
        case 'LOAD_ARTICLES':
            return { ...state, loading: true };
        default:
            return state;
    }
}
""".strip()
    )

    (tmp_path / "package.json").write_text('{"name": "conduit"}')
    return tmp_path


class TestCodeIndex:
    def test_scan_finds_files(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        paths = list(idx._files.keys())
        assert len(paths) >= 3
        assert any("agent.ts" in p for p in paths)

    def test_find_symbol(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        results = idx.find_symbol("ArticleService")
        assert len(results) >= 1
        assert results[0].kind == "class"

    def test_find_interface(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        results = idx.find_symbol("Article")
        assert len(results) >= 1
        kinds = {r.kind for r in results}
        assert "interface" in kinds

    def test_find_function(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        results = idx.find_symbol("fetchArticles")
        assert len(results) >= 1
        assert results[0].kind == "function"

    def test_find_reducer(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        results = idx.find_symbol("articleReducer")
        assert len(results) >= 1

    def test_to_context_summary(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        summary = idx.to_context_summary()
        assert "ArticleService" in summary
        assert "Article" in summary
        assert len(summary) < 5000

    def test_get_dependents(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        dependents = idx.get_dependents("src/models/article.ts")
        assert any("agent.ts" in d for d in dependents)
        assert any("reducer.ts" in d for d in dependents)

    def test_empty_project(self, tmp_path):
        idx = CodeIndex(tmp_path)
        idx.scan()
        assert len(idx._files) == 0
        assert idx.to_context_summary() == ""
