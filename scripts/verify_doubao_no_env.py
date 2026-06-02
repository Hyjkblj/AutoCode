from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _clear_llm_env() -> None:
    for key in (
        "LLM_BACKEND",
        "LLM_MODEL",
        "LLM_TEMPERATURE",
        "LLM_TIMEOUT_SECONDS",
        "LLM_CONFIG_PATH",
        "LLM_PROFILE",
        "OPENAI_API_KEY",
        "ARK_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_CHAT_URL",
        "ANTHROPIC_API_KEY",
    ):
        os.environ.pop(key, None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Volcengine Ark call without environment variables.")
    parser.add_argument(
        "--config",
        default="python-agent/configs/doubao-seed-2.0-code-high-perf.json",
        help="Path to llm profile json (relative to repo root by default).",
    )
    parser.add_argument(
        "--prompt",
        default="Reply exactly with: OK",
        help="Prompt sent to model.",
    )
    args = parser.parse_args()

    root = _project_root()
    config_path = (root / args.config).resolve()
    if not config_path.exists():
        print(f"[ERROR] config not found: {config_path}")
        return 2

    _clear_llm_env()

    sys.path.insert(0, str((root / "python-agent").resolve()))
    from llm.llm_client import LLMClient, LLMClientError  # noqa: WPS433

    client = LLMClient(config_path=str(config_path))
    print(f"[INFO] backend={client.settings.backend} model={client.settings.model}")
    print(f"[INFO] config={config_path}")
    print(f"[INFO] required_key_name={client.required_key_name()}")

    try:
        content = client.generate(args.prompt)
    except LLMClientError as exc:
        print(f"[FAIL] call failed: {exc}")
        return 1

    print("[PASS] call succeeded")
    print("[RESPONSE]")
    print(content.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
