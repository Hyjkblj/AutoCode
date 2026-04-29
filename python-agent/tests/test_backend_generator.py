from __future__ import annotations

from generators.backend_generator import BackendGenerator


def test_backend_generator_uses_managed_requirements_template() -> None:
    result = BackendGenerator().generate("build a todo backend")

    assert result.files["requirements.txt"] == "flask==3.0.3\nflask-cors==4.0.1\n"


def test_backend_generator_creates_expected_backend_files() -> None:
    result = BackendGenerator().generate("build a user backend")

    assert "backend/app.py" in result.files
    assert "backend/models.py" in result.files
    assert "requirements.txt" in result.files
    assert "README.generated.md" in result.files
