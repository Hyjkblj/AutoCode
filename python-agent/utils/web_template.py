from __future__ import annotations

import json
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
SUPPORTED_TEMPLATE_IDS: tuple[str, ...] = ("starter", "product")


@dataclass(frozen=True)
class WebTemplateResult:
    files: dict[str, str]
    used_fallback: bool
    reason: str
    template_id: str


class WebTemplateGenerator:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def generate(self, prompt: str, target: str = "web", template_id: str | None = None) -> WebTemplateResult:
        normalized_target = (target or "web").strip().lower()
        if normalized_target != "web":
            raise ValueError("unsupported_target")
        selected_template = _resolve_template_id(template_id)
        prompt_text = (prompt or "").strip()

        if self.llm_client.is_configured():
            try:
                llm_files = self._generate_via_llm(prompt_text, selected_template)
                return WebTemplateResult(
                    files=llm_files,
                    used_fallback=False,
                    reason="llm_generated",
                    template_id=selected_template,
                )
            except Exception as exc:  # noqa: BLE001
                fallback = _fallback_files(prompt_text, selected_template)
                return WebTemplateResult(
                    files=fallback,
                    used_fallback=True,
                    reason=f"llm_fallback:{exc}",
                    template_id=selected_template,
                )

        fallback = _fallback_files(prompt_text, selected_template)
        return WebTemplateResult(
            files=fallback,
            used_fallback=True,
            reason="llm_not_configured",
            template_id=selected_template,
        )

    def _generate_via_llm(self, prompt: str, template_id: str) -> dict[str, str]:
        system_prompt = (
            "You generate a minimal static web app. Return JSON only with keys: "
            "index.html, styles.css, app.js, README.generated.md. "
            "Each key value must be full file content as a string."
        )
        raw = self.llm_client.generate(
            f"Template id: {template_id}\nUser requirement:\n{prompt}",
            system_prompt=system_prompt,
        )
        parsed = _parse_llm_response(raw)
        files = _normalize_files(parsed)
        missing = [name for name in REQUIRED_WEB_FILES if name not in files]
        if missing:
            raise ValueError(f"missing required files from llm: {','.join(missing)}")
        return files


def _parse_llm_response(raw: str) -> Any:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty llm response")
    data = json.loads(text)
    if isinstance(data, dict) and isinstance(data.get("files"), dict):
        return data["files"]
    return data


def _normalize_files(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        raise ValueError("llm output must be an object")
    files: dict[str, str] = {}
    for name in REQUIRED_WEB_FILES:
        value = data.get(name)
        if isinstance(value, str) and value.strip():
            files[name] = value
    return files


def _resolve_template_id(template_id: str | None) -> str:
    selected = (template_id or "starter").strip().lower()
    if selected not in SUPPORTED_TEMPLATE_IDS:
        raise ValueError("unsupported_template_id")
    return selected


def _fallback_files(prompt: str, template_id: str) -> dict[str, str]:
    safe_prompt = prompt if prompt else "build a simple interactive web page"
    title = "Generated Web App" if template_id == "starter" else "Generated Product Page"
    subtitle = escape(safe_prompt)
    prompt_json = json.dumps(safe_prompt, ensure_ascii=False)
    theme_color = "#2f6bff" if template_id == "starter" else "#0f9d58"
    surface_gradient = "linear-gradient(145deg, #f6f8ff 0%, #eef3ff 100%)"
    if template_id == "product":
        surface_gradient = "linear-gradient(145deg, #f2fff7 0%, #e8fff1 100%)"

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
  background: {surface_gradient};
  color: #1e2a3a;
}}

.app {{
  max-width: 720px;
  margin: 48px auto;
  padding: 24px;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 18px 40px rgba(32, 64, 128, 0.12);
}}

h1 {{
  margin-top: 0;
}}

button {{
  margin-top: 16px;
  padding: 10px 16px;
  border: 0;
  border-radius: 10px;
  background: {theme_color};
  color: #fff;
  cursor: pointer;
}}

pre {{
  margin-top: 16px;
  padding: 12px;
  border-radius: 10px;
  background: #0f172a;
  color: #e2e8f0;
  min-height: 72px;
}}
"""

    app_js = f"""const promptText = {prompt_json};
const actionBtn = document.getElementById("action");
const output = document.getElementById("output");

actionBtn.addEventListener("click", () => {{
  output.textContent = [
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

Template: `{template_id}`

## Files

- `index.html`
- `styles.css`
- `app.js`

## Run

Open `index.html` in a browser.
"""

    return {
        "index.html": index_html,
        "styles.css": styles_css,
        "app.js": app_js,
        "README.generated.md": readme,
    }
