from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GeneratedTest:
    file_path: str
    content: str
    framework: str
    test_count: int


class TestGenerator:
    _SYSTEM_PROMPT = (
        "You are a test generation assistant. Given a source file and its content, "
        "generate unit tests using the detected test framework. "
        "Output ONLY the test code, no explanations."
    )

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm_client = llm_client

    def detect_test_framework(self, workspace: Path) -> str:
        pkg = workspace / "package.json"
        if not pkg.exists():
            return "jest"
        try:
            data = json.loads(pkg.read_text())
            dev_deps = data.get("devDependencies", {})
            if "vitest" in dev_deps:
                return "vitest"
            if "mocha" in dev_deps:
                return "mocha"
            if "jest" in dev_deps:
                return "jest"
        except (json.JSONDecodeError, KeyError):
            pass
        return "jest"

    def generate_tests(self, workspace: Path, changed_files: list[str], prompt: str) -> list[GeneratedTest]:
        if not self.llm_client:
            return []
        framework = self.detect_test_framework(workspace)
        results = []
        for file_path in changed_files:
            full_path = workspace / file_path
            if not full_path.exists():
                continue
            content = full_path.read_text(encoding="utf-8", errors="replace")
            user_msg = (
                f"Framework: {framework}\nFile: {file_path}\n"
                f"Content:\n{content}\n\nTask: {prompt}\n\n"
                f"Generate comprehensive unit tests for this file."
            )
            try:
                test_code = self.llm_client.generate(user_msg, system_prompt=self._SYSTEM_PROMPT)
                test_count = test_code.count("it(") + test_code.count("test(")
                test_file = file_path.replace(".ts", ".test.ts").replace(".js", ".test.js")
                results.append(GeneratedTest(file_path=test_file, content=test_code, framework=framework, test_count=max(test_count, 1)))
            except Exception:
                continue
        return results
