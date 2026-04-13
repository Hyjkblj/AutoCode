from __future__ import annotations

import json
import os
from dataclasses import dataclass
from html import escape
from typing import Any

from llm.llm_client import LLMClient


REQUIRED_WEB_FILES: tuple[str, ...] = (
    "index.html",
    "styles.css",
    "app.js",
    "README.generated.md",
)


@dataclass(frozen=True)
class WebTemplateResult:
    files: dict[str, str]
    used_fallback: bool
    reason: str
    theme: str = "clean"


class WebTemplateGenerator:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def generate(self, prompt: str, target: str = "web") -> WebTemplateResult:
        normalized_target = (target or "web").strip().lower()
        if normalized_target != "web":
            raise ValueError("unsupported_target")

        prompt_text = (prompt or "").strip()

        if self.llm_client.is_configured():
            try:
                llm_files, llm_theme = self._generate_via_llm(prompt_text)
                return WebTemplateResult(
                    files=llm_files,
                    used_fallback=False,
                    reason="llm_generated",
                    theme=llm_theme,
                )
            except Exception as exc:  # noqa: BLE001
                fallback, fallback_theme = _fallback_files(prompt_text)
                return WebTemplateResult(
                    files=fallback,
                    used_fallback=True,
                    reason=f"llm_fallback:{exc}",
                    theme=fallback_theme,
                )

        fallback, fallback_theme = _fallback_files(prompt_text)
        return WebTemplateResult(
            files=fallback,
            used_fallback=True,
            reason="llm_not_configured",
            theme=fallback_theme,
        )

    def _generate_via_llm(self, prompt: str) -> tuple[dict[str, str], str]:
        system_prompt = _build_system_prompt(_prompt_mode())
        raw = self.llm_client.generate(prompt, system_prompt=system_prompt)
        parsed = _parse_llm_response(raw)
        source = parsed.get("files") if isinstance(parsed, dict) and isinstance(parsed.get("files"), dict) else parsed
        files = _normalize_files(source)
        missing = [name for name in REQUIRED_WEB_FILES if name not in files]
        if missing:
            raise ValueError(f"missing required files from llm: {','.join(missing)}")
        theme = _normalize_theme(parsed.get("theme") if isinstance(parsed, dict) else None, prompt)
        return files, theme


def _parse_llm_response(raw: str) -> Any:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty llm response")
    data = _loads_json_relaxed(text)
    return data


def _normalize_files(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        raise ValueError("llm output must be an object")
    lowered = {str(k).strip().lower(): v for k, v in data.items()}
    files: dict[str, str] = {}
    aliases: dict[str, tuple[str, ...]] = {
        "index.html": ("index.html", "index"),
        "styles.css": ("styles.css", "style.css", "styles"),
        "app.js": ("app.js", "main.js", "script.js", "script"),
        "README.generated.md": ("readme.generated.md", "readme.md", "readme"),
    }
    for name in REQUIRED_WEB_FILES:
        keys = aliases[name]
        value = None
        for key in keys:
            candidate = lowered.get(key.lower())
            if isinstance(candidate, str) and candidate.strip():
                value = candidate
                break
        if isinstance(value, str) and value.strip():
            files[name] = value
    return files


def _fallback_files(prompt: str) -> dict[str, str]:
    safe_prompt = prompt if prompt else "build a simple interactive web page"
    theme = _normalize_theme(None, safe_prompt)
    palette = _theme_palette(theme)
    title = "Generated Web App"
    subtitle = escape(safe_prompt)
    prompt_json = json.dumps(safe_prompt, ensure_ascii=False)

    index_html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body>
    <main class="app">
      <h1>{title}</h1>
      <p id="subtitle">{subtitle}</p>
      <button id="action">Run Demo Action</button>
      <pre id="output"></pre>
    </main>
    <script src="app.js"></script>
  </body>
</html>
"""

    styles_css = f"""* {{
  box-sizing: border-box;
}}

body {{
  margin: 0;
  min-height: 100vh;
  font-family: "Segoe UI", sans-serif;
  background: {palette["bg"]};
  color: {palette["text"]};
}}

.app {{
  max-width: 720px;
  margin: 48px auto;
  padding: 24px;
  background: {palette["panel"]};
  border-radius: 16px;
  box-shadow: {palette["shadow"]};
}}

h1 {{
  margin-top: 0;
}}

button {{
  margin-top: 16px;
  padding: 10px 16px;
  border: 0;
  border-radius: 10px;
  background: {palette["button_bg"]};
  color: {palette["button_text"]};
  cursor: pointer;
}}

pre {{
  margin-top: 16px;
  padding: 12px;
  border-radius: 10px;
  background: {palette["code_bg"]};
  color: {palette["code_text"]};
  min-height: 72px;
}}
"""

    app_js = f"""const promptText = {prompt_json};
const theme = {json.dumps(theme, ensure_ascii=False)};
const actionBtn = document.getElementById("action");
const output = document.getElementById("output");

actionBtn.addEventListener("click", () => {{
  output.textContent = [
    "Theme:",
    theme,
    "",
    "Prompt:",
    promptText,
    "",
    "Status:",
    "Fallback template generated successfully."
  ].join("\\n");
}});
"""

    readme = f"""# Generated Web App

This project was generated from natural language prompt:

> {safe_prompt}

Theme: `{theme}`

## Files

- `index.html`
- `styles.css`
- `app.js`

## Run

Open `index.html` in a browser.
"""

    files = {
        "index.html": index_html,
        "styles.css": styles_css,
        "app.js": app_js,
        "README.generated.md": readme,
    }
    return files, theme


def _loads_json_relaxed(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    code_block = _extract_code_block_content(text)
    if code_block:
        try:
            return json.loads(code_block)
        except json.JSONDecodeError:
            pass

    raise ValueError("llm output is not valid json")


def _extract_code_block_content(text: str) -> str:
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


def _normalize_theme(raw_theme: object, prompt: str) -> str:
    normalized = str(raw_theme or "").strip().lower()
    if normalized in {"clean", "modern", "dark", "playful", "enterprise"}:
        return normalized
    text = (prompt or "").strip().lower()
    if any(k in text for k in ("enterprise", "dashboard", "管理系统", "企业")):
        return "enterprise"
    if any(k in text for k in ("dark", "neon", "科技", "酷", "高级")):
        return "dark"
    if any(k in text for k in ("playful", "cute", "可爱", "有趣")):
        return "playful"
    if any(k in text for k in ("modern", "gradient", "modern ui")):
        return "modern"
    return "clean"


def _theme_palette(theme: str) -> dict[str, str]:
    palettes: dict[str, dict[str, str]] = {
        "clean": {
            "bg": "linear-gradient(145deg, #f6f8ff 0%, #eef3ff 100%)",
            "text": "#1e2a3a",
            "panel": "#ffffff",
            "shadow": "0 18px 40px rgba(32, 64, 128, 0.12)",
            "button_bg": "#2f6bff",
            "button_text": "#ffffff",
            "code_bg": "#0f172a",
            "code_text": "#e2e8f0",
        },
        "modern": {
            "bg": "linear-gradient(135deg, #eef2ff 0%, #dbeafe 50%, #fae8ff 100%)",
            "text": "#172554",
            "panel": "#ffffff",
            "shadow": "0 20px 44px rgba(37, 99, 235, 0.18)",
            "button_bg": "#2563eb",
            "button_text": "#ffffff",
            "code_bg": "#111827",
            "code_text": "#e5e7eb",
        },
        "dark": {
            "bg": "radial-gradient(circle at top, #111827 0%, #030712 75%)",
            "text": "#d1d5db",
            "panel": "#111827",
            "shadow": "0 20px 50px rgba(0, 0, 0, 0.45)",
            "button_bg": "#22d3ee",
            "button_text": "#0b1120",
            "code_bg": "#020617",
            "code_text": "#93c5fd",
        },
        "playful": {
            "bg": "linear-gradient(140deg, #fff7ed 0%, #ffe4e6 45%, #e0f2fe 100%)",
            "text": "#7c2d12",
            "panel": "#fffaf5",
            "shadow": "0 16px 38px rgba(251, 113, 133, 0.2)",
            "button_bg": "#fb7185",
            "button_text": "#ffffff",
            "code_bg": "#1f2937",
            "code_text": "#fde68a",
        },
        "enterprise": {
            "bg": "linear-gradient(160deg, #f8fafc 0%, #e2e8f0 100%)",
            "text": "#0f172a",
            "panel": "#ffffff",
            "shadow": "0 12px 28px rgba(15, 23, 42, 0.16)",
            "button_bg": "#0f172a",
            "button_text": "#ffffff",
            "code_bg": "#0b1220",
            "code_text": "#cbd5e1",
        },
    }
    return palettes.get(theme, palettes["clean"])


def _prompt_mode() -> str:
    mode = os.getenv("WEB_TEMPLATE_PROMPT_MODE", "contract").strip().lower()
    if mode in {"direct", "passthrough", "raw"}:
        return "direct"
    return "contract"


def _build_system_prompt(mode: str) -> str:
    if mode == "direct":
        return (
            "You are an expert frontend engineer and product designer.\n"
            "Treat the user's prompt as the primary requirement source.\n"
            "Build a concrete, non-generic static web app that matches requested features.\n"
            "Avoid placeholder boilerplate.\n\n"
            "Return JSON only with keys:\n"
            "theme, index.html, styles.css, app.js, README.generated.md\n"
            "theme must be one of: clean, modern, dark, playful, enterprise.\n"
            "Each file value must be full file content as a string."
        )

    return (
        "You generate a minimal static web app based on a predefined system architecture.\n\n"
        "ARCHITECTURE_CONTRACT:\n"
        "- system_type: static_web_app_v1 (fixed)\n"
        "- modules: ui_shell, interaction_logic, docs (fixed)\n"
        "- required_files: index.html, styles.css, app.js, README.generated.md (fixed)\n\n"
        "UI THEME LAYER:\n"
        "You MUST apply one theme: clean, modern, dark, playful, enterprise.\n\n"
        "STRICT RULES:\n"
        "1) system_type and modules are fixed and must not be changed.\n"
        "2) functionality must follow user requirements.\n"
        "3) theme only changes visual design (css/layout/colors).\n"
        "4) do not change business logic because of theme.\n"
        "5) if user does not specify theme, infer from tone:\n"
        '   - "酷/高级/科技" -> dark or modern\n'
        '   - "简单/干净" -> clean\n'
        '   - "企业/管理系统" -> enterprise\n'
        '   - "可爱/有趣" -> playful\n\n'
        "OUTPUT FORMAT:\n"
        "Return JSON only with keys:\n"
        "theme, index.html, styles.css, app.js, README.generated.md\n"
        "Each file key value must be full file content as a string."
    )
