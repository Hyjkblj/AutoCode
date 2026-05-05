from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from html import escape
from typing import Any

from llm.llm_client import LLMClient
from utils.observability import ensure_task_observability


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

    def generate(self, prompt: str, target: str = "web", task: dict[str, Any] | None = None) -> WebTemplateResult:
        normalized_target = (target or "web").strip().lower()
        if normalized_target != "web":
            raise ValueError("unsupported_target")

        prompt_text = (prompt or "").strip()

        if self.llm_client.is_configured():
            attempt_cursor = self.llm_client.cache_event_cursor()
            try:
                llm_files, llm_theme = self._generate_via_llm(prompt_text, task=task)
                return WebTemplateResult(
                    files=llm_files,
                    used_fallback=False,
                    reason="llm_generated",
                    theme=llm_theme,
                )
            except Exception as exc:  # noqa: BLE001
                self.llm_client.discard_cache_entries_since(attempt_cursor, reason="invalid_web_template_response")
                if task is not None:
                    self.llm_client.record_cache_metrics(
                        ensure_task_observability(task, engine=str(task.get("_agentEngine", "")).strip()),
                        stage="WebTemplateGenerator",
                        backend=self.llm_client.settings.backend,
                    )
                if _should_retry_llm_generation(exc):
                    retry_cursor = self.llm_client.cache_event_cursor()
                    try:
                        llm_files, llm_theme = self._generate_via_llm(
                            _build_retry_prompt(prompt_text),
                            task=task,
                            is_retry=True,
                        )
                        return WebTemplateResult(
                            files=llm_files,
                            used_fallback=False,
                            reason="llm_generated_retry",
                            theme=llm_theme,
                        )
                    except Exception as retry_exc:  # noqa: BLE001
                        self.llm_client.discard_cache_entries_since(
                            retry_cursor,
                            reason="invalid_web_template_retry_response",
                        )
                        if task is not None:
                            self.llm_client.record_cache_metrics(
                                ensure_task_observability(task, engine=str(task.get("_agentEngine", "")).strip()),
                                stage="WebTemplateGenerator",
                                backend=self.llm_client.settings.backend,
                            )
                        fallback, fallback_theme = _fallback_files(prompt_text)
                        return WebTemplateResult(
                            files=fallback,
                            used_fallback=True,
                            reason=f"llm_fallback:retry_failed:{retry_exc}",
                            theme=fallback_theme,
                        )

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

    def _generate_via_llm(
        self,
        prompt: str,
        *,
        task: dict[str, Any] | None = None,
        is_retry: bool = False,
    ) -> tuple[dict[str, str], str]:
        system_prompt = _build_system_prompt(_prompt_mode())
        if is_retry:
            system_prompt = (
                f"{system_prompt}\n\n"
                "RETRY MODE:\n"
                "Return pure JSON only; no markdown fences, comments, or explanation text."
            )
        observation = None
        cache_cursor = 0
        raw = ""
        if task is not None:
            observation = ensure_task_observability(task, engine=str(task.get("_agentEngine", "")).strip())
            cache_cursor = self.llm_client.cache_event_cursor()
        try:
            raw = self.llm_client.generate(prompt, system_prompt=system_prompt)
            parsed = _parse_llm_response(raw)
            source = parsed.get("files") if isinstance(parsed, dict) and isinstance(parsed.get("files"), dict) else parsed
            files = _normalize_files(source)
            missing = [name for name in REQUIRED_WEB_FILES if name not in files]
            if missing:
                raise ValueError(f"missing required files from llm: {','.join(missing)}")
            theme = _normalize_theme(parsed.get("theme") if isinstance(parsed, dict) else None, prompt)
            return files, theme
        finally:
            if observation is not None:
                self.llm_client.record_cache_metrics(
                    observation,
                    stage="WebTemplateGenerator",
                    backend=self.llm_client.settings.backend,
                    since_sequence=cache_cursor,
                )


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


def _fallback_files(prompt: str) -> tuple[dict[str, str], str]:
    safe_prompt = prompt if prompt else "build a simple interactive web page"
    theme = _normalize_theme(None, safe_prompt)
    palette = _theme_palette(theme)

    seed = _prompt_seed(safe_prompt)
    accent = _accent_color(seed)
    layout = _select_fallback_layout(safe_prompt, seed)
    cards = _fallback_cards(layout)
    cards_html = "\n".join(
        f'        <article class="panel-card"><h3>{escape(title)}</h3><p>{escape(desc)}</p></article>'
        for title, desc in cards
    )
    cta_text = _fallback_cta_text(layout)
    layout_label = layout.replace("-", " ").title()

    title = "Generated Web App"
    subtitle = escape(safe_prompt)
    prompt_json = json.dumps(safe_prompt, ensure_ascii=False)
    theme_json = json.dumps(theme, ensure_ascii=False)
    layout_json = json.dumps(layout, ensure_ascii=False)
    accent_json = json.dumps(accent, ensure_ascii=False)

    index_html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body>
    <main class="app layout-{layout}">
      <h1>{title}</h1>
      <p id="subtitle">{subtitle}</p>
      <p class="meta">Fallback mode - {layout_label} layout - {theme} theme</p>
      <section class="panels">
{cards_html}
      </section>
      <button id="action">{cta_text}</button>
      <pre id="output"></pre>
    </main>
    <script src="app.js"></script>
  </body>
</html>
"""

    styles_css = f"""* {{
  box-sizing: border-box;
}}

:root {{
  --accent: {accent};
}}

body {{
  margin: 0;
  min-height: 100vh;
  font-family: "Segoe UI", sans-serif;
  background: {palette["bg"]};
  color: {palette["text"]};
}}

.app {{
  max-width: 880px;
  margin: 48px auto;
  padding: 24px;
  background: {palette["panel"]};
  border-radius: 16px;
  box-shadow: {palette["shadow"]};
  border-top: 6px solid var(--accent);
}}

h1 {{
  margin-top: 0;
}}

.meta {{
  margin: 8px 0 16px;
  color: {palette["text"]};
  opacity: 0.78;
}}

.panels {{
  display: grid;
  gap: 12px;
  margin: 12px 0 16px;
}}

.layout-dashboard .panels {{
  grid-template-columns: 1.4fr 1fr;
}}

.layout-showcase .panels {{
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}}

.layout-workspace .panels {{
  grid-template-columns: 1fr;
}}

.panel-card {{
  padding: 14px;
  border-radius: 12px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  background: linear-gradient(170deg, #ffffff 0%, rgba(255, 255, 255, 0.82) 100%);
}}

.panel-card h3 {{
  margin: 0 0 8px;
  font-size: 1rem;
}}

.panel-card p {{
  margin: 0;
  line-height: 1.5;
  opacity: 0.86;
}}

button {{
  margin-top: 16px;
  padding: 10px 16px;
  border: 0;
  border-radius: 10px;
  background: var(--accent);
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

@media (max-width: 720px) {{
  .layout-dashboard .panels {{
    grid-template-columns: 1fr;
  }}
}}
"""

    app_js = f"""const promptText = {prompt_json};
const theme = {theme_json};
const layout = {layout_json};
const accent = {accent_json};
const actionBtn = document.getElementById("action");
const output = document.getElementById("output");

actionBtn.addEventListener("click", () => {{
  output.textContent = [
    "Theme:",
    theme,
    "",
    "Layout:",
    layout,
    "",
    "Accent:",
    accent,
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
Layout: `{layout}`

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
    if any(k in text for k in ("enterprise", "dashboard", "admin", "管理系统", "企业")):
        return "enterprise"
    if any(k in text for k in ("dark", "neon", "tech", "科技", "高级")):
        return "dark"
    if any(k in text for k in ("playful", "cute", "fun", "可爱", "有趣")):
        return "playful"
    if any(k in text for k in ("modern", "gradient", "modern ui", "简洁", "简约", "clean")):
        return "modern"
    return "clean"


def _prompt_seed(prompt: str) -> int:
    digest = hashlib.sha256((prompt or "").encode("utf-8")).digest()
    return int.from_bytes(digest[:2], byteorder="big", signed=False)


def _accent_color(seed: int) -> str:
    hue = seed % 360
    sat = 72 + (seed % 14)
    light = 46 + (seed % 8)
    return f"hsl({hue} {sat}% {light}%)"


def _select_fallback_layout(prompt: str, seed: int) -> str:
    text = (prompt or "").strip().lower()
    if any(k in text for k in ("dashboard", "admin", "analytics", "report", "报表", "管理", "仪表盘")):
        return "dashboard"
    if any(k in text for k in ("gallery", "portfolio", "showcase", "photography", "展示", "作品", "相册")):
        return "showcase"
    if any(k in text for k in ("todo", "task", "workspace", "editor", "planner", "任务", "待办", "工作台")):
        return "workspace"
    return ("dashboard", "showcase", "workspace")[seed % 3]


def _fallback_cards(layout: str) -> list[tuple[str, str]]:
    if layout == "dashboard":
        return [
            ("Status Overview", "Track key metrics and recent activity in a compact control view."),
            ("Daily Highlights", "Pin updates and trends that matter right now."),
            ("Action Queue", "Prioritize next actions with clear visual grouping."),
        ]
    if layout == "showcase":
        return [
            ("Hero Section", "Use strong visuals and headline copy to frame the story."),
            ("Feature Tiles", "Present core modules as scan-friendly cards."),
            ("Call To Action", "Guide visitors to the primary conversion path."),
        ]
    return [
        ("Workspace", "Focus on actionable items and short feedback loops."),
        ("Task Board", "Keep progress visible with lightweight structure."),
        ("Quick Notes", "Capture context near the work area for fast iteration."),
    ]


def _fallback_cta_text(layout: str) -> str:
    if layout == "dashboard":
        return "Refresh Insights"
    if layout == "showcase":
        return "Preview Experience"
    return "Run Workspace Check"


def _build_retry_prompt(prompt: str) -> str:
    requirement = (prompt or "").strip() or "build a simple interactive web page"
    return (
        "Return one compact JSON object only with keys:\n"
        "theme, index.html, styles.css, app.js, README.generated.md\n"
        "Do not wrap in markdown or code fences.\n"
        "Requirement:\n"
        f"{requirement}"
    )


def _should_retry_llm_generation(exc: Exception) -> bool:
    text = str(exc).strip().lower()
    if not text:
        return False
    return "json" in text or "missing required files" in text


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
    mode = os.getenv("WEB_TEMPLATE_PROMPT_MODE", "direct").strip().lower()
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
        "5) if user does not specify theme, infer from tone.\n\n"
        "OUTPUT FORMAT:\n"
        "Return JSON only with keys:\n"
        "theme, index.html, styles.css, app.js, README.generated.md\n"
        "Each file key value must be full file content as a string."
    )
