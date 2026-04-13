from __future__ import annotations

import json
import zipfile

from llm.llm_client import LLMClient
from utils.artifact_utils import build_export_zip
from utils.web_template import WebTemplateGenerator


def test_web_template_generator_uses_llm_json(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    files = {
        "index.html": "<html></html>",
        "styles.css": "body{}",
        "app.js": "console.log('ok')",
        "README.generated.md": "# demo",
    }
    fenced = "```json\n" + json.dumps({"files": files}) + "\n```"

    def provider(backend, messages, model, temperature):  # noqa: ANN001
        return fenced

    generator = WebTemplateGenerator(llm_client=LLMClient(response_provider=provider))
    result = generator.generate("build a page", target="web")

    assert result.used_fallback is False
    assert result.files == files


def test_build_export_zip_packages_generated_files(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "index.html").write_text("<html></html>", encoding="utf-8")
    (workspace / "styles.css").write_text("body{}", encoding="utf-8")
    (workspace / "app.js").write_text("console.log('ok')", encoding="utf-8")
    (workspace / "README.generated.md").write_text("# demo", encoding="utf-8")

    bundle = build_export_zip(workspace, ["index.html", "styles.css", "app.js", "README.generated.md"])

    assert bundle.file_name == "export.zip"
    assert bundle.file_path.exists()
    assert bundle.artifact_id.startswith("art_zip_")
    assert bundle.size_bytes > 0
    assert len(bundle.sha256) == 64

    with zipfile.ZipFile(bundle.file_path, "r") as zipf:
        names = sorted(zipf.namelist())
    assert names == ["README.generated.md", "app.js", "index.html", "styles.css"]


def test_web_template_fallback_uses_prompt_specific_layouts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    profile = {
        "provider": "openai",
        "api": {"auth_header": "Bearer ${OPENAI_API_KEY}"},
        "request": {"model": "gpt-4.1-mini"},
        "compat_env": {"LLM_BACKEND": "openai"},
    }
    profile_path = tmp_path / "llm-profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    monkeypatch.setenv("LLM_CONFIG_PATH", str(profile_path))

    generator = WebTemplateGenerator()
    dashboard = generator.generate("build analytics dashboard", target="web")
    showcase = generator.generate("build portfolio showcase", target="web")

    assert dashboard.used_fallback is True
    assert showcase.used_fallback is True
    assert 'class="app layout-dashboard"' in dashboard.files["index.html"]
    assert 'class="app layout-showcase"' in showcase.files["index.html"]


def test_web_template_retries_once_when_llm_returns_invalid_json(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    files = {
        "index.html": "<html>retry</html>",
        "styles.css": "body{background:#fff;}",
        "app.js": "console.log('retry');",
        "README.generated.md": "# retry",
    }
    responses = iter(
        [
            "not json",
            json.dumps({"files": files}),
        ]
    )

    def provider(backend, messages, model, temperature):  # noqa: ANN001
        return next(responses)

    generator = WebTemplateGenerator(llm_client=LLMClient(response_provider=provider))
    result = generator.generate("build a page", target="web")

    assert result.used_fallback is False
    assert result.reason == "llm_generated_retry"
    assert result.files == files


def test_web_template_fallback_after_retry_failure(monkeypatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    responses = iter(["not json", "still not json"])

    def provider(backend, messages, model, temperature):  # noqa: ANN001
        return next(responses)

    generator = WebTemplateGenerator(llm_client=LLMClient(response_provider=provider))
    result = generator.generate("build analytics dashboard", target="web")

    assert result.used_fallback is True
    assert result.reason.startswith("llm_fallback:retry_failed:")
