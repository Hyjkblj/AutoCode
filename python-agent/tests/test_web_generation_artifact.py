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
