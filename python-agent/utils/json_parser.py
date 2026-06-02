"""Relaxed JSON parser for LLM output.

Handles common LLM response quirks: markdown fences, extra text before/after JSON,
code block wrappers, and minor formatting issues.
"""
from __future__ import annotations

import json
from typing import Any


def loads_json_relaxed(text: str) -> Any:
    """Parse JSON from LLM output, handling markdown fences and extra text."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("empty llm response")

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting the outermost { ... } block
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Try extracting from markdown code fences
    code_block = _extract_code_block_content(cleaned)
    if code_block:
        try:
            return json.loads(code_block)
        except json.JSONDecodeError:
            pass

    raise ValueError("llm output is not valid json")


def _extract_code_block_content(text: str) -> str:
    """Extract content from the first markdown code block."""
    marker = "```"
    start = text.find(marker)
    if start < 0:
        return ""
    end = text.find(marker, start + len(marker))
    if end < 0:
        return ""
    inner = text[start + len(marker) : end].strip()
    if inner.startswith("json"):
        inner = inner[len("json") :].strip()
    return inner
