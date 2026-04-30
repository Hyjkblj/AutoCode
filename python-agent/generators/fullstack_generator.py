from __future__ import annotations

from typing import Any

from generators import GeneratedProjectResult
from generators.backend_generator import BackendGenerator
from utils.web_template import WebTemplateGenerator


class FullstackGenerator:
    def __init__(
        self,
        *,
        backend_generator: BackendGenerator | None = None,
        web_template_generator: WebTemplateGenerator | None = None,
    ) -> None:
        self.backend_generator = backend_generator or BackendGenerator()
        self.web_template_generator = web_template_generator or WebTemplateGenerator()

    def generate(self, prompt: str, task: dict[str, Any] | None = None) -> GeneratedProjectResult:
        backend = self.backend_generator.generate(prompt)
        frontend = self.web_template_generator.generate(prompt, target="web", task=task)

        files: dict[str, str] = {}
        for relative, content in frontend.files.items():
            files[f"frontend/{relative}"] = content
        for relative, content in backend.files.items():
            if relative == "README.generated.md":
                continue
            files[relative] = content
        files["README.generated.md"] = _build_readme(prompt)

        return GeneratedProjectResult(
            files=files,
            used_fallback=backend.used_fallback or frontend.used_fallback,
            reason=f"{backend.reason};{frontend.reason}",
        )


def _build_readme(prompt: str) -> str:
    return f"""# Generated Fullstack App

This project was generated from:

> {prompt.strip() or "Build a fullstack application"}

## Structure

- `frontend/` static client files
- `backend/` Flask + SQLite API
- `requirements.txt` backend dependencies

## Run

```bash
pip install -r requirements.txt
python backend/app.py
```

Then open `frontend/index.html` or host the frontend with a static file server.
"""
