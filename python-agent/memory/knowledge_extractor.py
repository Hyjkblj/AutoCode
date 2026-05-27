from __future__ import annotations

import json
from typing import Any


class KnowledgeExtractor:
    _FILE_SUMMARY_PROMPT = (
        "Summarize this source file in 2-3 sentences. Include: what it does, "
        "key classes/functions, and dependencies. Be concise and factual."
    )
    _ARCH_PROMPT = (
        "Given this project's code index summary, extract: "
        "1. Overall architecture pattern 2. Key modules and their responsibilities "
        "3. Entry points and data flow. "
        'Respond as JSON: {"architecture": str, "modules": [str], "entry_points": [str], "data_flow": str}'
    )

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm_client = llm_client

    def extract_file_summary(self, file_path: str, content: str) -> str:
        if not self.llm_client:
            return ""
        user_msg = f"File: {file_path}\n\n```\n{content[:3000]}\n```"
        try:
            return self.llm_client.generate(user_msg, system_prompt=self._FILE_SUMMARY_PROMPT).strip()
        except Exception:
            return ""

    def extract_project_architecture(self, code_index: Any) -> dict:
        if not self.llm_client:
            return {}
        summary = code_index.to_context_summary()
        if not summary:
            return {}
        try:
            raw = self.llm_client.generate(summary, system_prompt=self._ARCH_PROMPT)
            return json.loads(raw)
        except (json.JSONDecodeError, Exception):
            return {}
