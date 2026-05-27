from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from generators.test_generator import GeneratedTest, TestGenerator

@pytest.fixture
def sample_project(tmp_path):
    (tmp_path / "package.json").write_text('{"devDependencies": {"jest": "^29.0.0"}}')
    src = tmp_path / "src"
    src.mkdir()
    (src / "math.ts").write_text("export function add(a: number, b: number): number { return a + b; }\nexport function multiply(a: number, b: number): number { return a * b; }")
    return tmp_path

class TestTestGenerator:
    def test_detect_jest_framework(self, sample_project):
        gen = TestGenerator()
        assert gen.detect_test_framework(sample_project) == "jest"

    def test_detect_no_framework(self, tmp_path):
        (tmp_path / "package.json").write_text('{"dependencies": {}}')
        gen = TestGenerator()
        assert gen.detect_test_framework(tmp_path) == "jest"

    def test_generate_tests(self, sample_project):
        llm = MagicMock()
        llm.generate.return_value = "import { add } from './math';\ndescribe('add', () => { it('adds', () => { expect(add(1,2)).toBe(3); }); });"
        gen = TestGenerator(llm_client=llm)
        results = gen.generate_tests(sample_project, ["src/math.ts"], "add unit tests")
        assert len(results) >= 1
        assert results[0].framework == "jest"
        assert "add" in results[0].content

    def test_generate_no_llm(self, sample_project):
        gen = TestGenerator(llm_client=None)
        assert gen.generate_tests(sample_project, ["src/math.ts"], "test") == []
