from __future__ import annotations

from pathlib import Path

from generators import GeneratedProjectResult


_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "requirements"
_GENERATED_BACKEND_REQUIREMENTS = _TEMPLATE_DIR / "generated-backend.txt"


class BackendGenerator:
    def generate(self, prompt: str) -> GeneratedProjectResult:
        config = _resource_config(prompt)
        files = {
            "backend/app.py": _build_app_py(config),
            "backend/models.py": _build_models_py(config),
            "requirements.txt": _load_generated_backend_requirements(),
            "README.generated.md": _build_readme(prompt, config),
        }
        return GeneratedProjectResult(files=files, used_fallback=True, reason="backend_template_generated")


def _load_generated_backend_requirements() -> str:
    fallback = "flask==3.0.3\nflask-cors==4.0.1\n"
    try:
        content = _GENERATED_BACKEND_REQUIREMENTS.read_text(encoding="utf-8")
    except OSError:
        return fallback

    normalized = content.strip()
    if not normalized:
        return fallback
    return f"{normalized}\n"


def _resource_config(prompt: str) -> dict[str, str]:
    text = (prompt or "").strip().lower()
    if any(token in text for token in ("todo", "待办", "task")):
        return {
            "table_name": "todos",
            "resource_name": "todo",
            "resource_label": "Todo",
            "list_field": "title",
            "secondary_field": "completed",
            "secondary_default": "0",
            "secondary_type": "INTEGER",
            "secondary_json_default": "false",
        }
    if any(token in text for token in ("blog", "博客", "post", "article")):
        return {
            "table_name": "posts",
            "resource_name": "post",
            "resource_label": "Post",
            "list_field": "title",
            "secondary_field": "content",
            "secondary_default": "''",
            "secondary_type": "TEXT",
            "secondary_json_default": '""',
        }
    if any(token in text for token in ("user", "用户", "account", "member")):
        return {
            "table_name": "users",
            "resource_name": "user",
            "resource_label": "User",
            "list_field": "name",
            "secondary_field": "email",
            "secondary_default": "''",
            "secondary_type": "TEXT",
            "secondary_json_default": '""',
        }
    return {
        "table_name": "records",
        "resource_name": "record",
        "resource_label": "Record",
        "list_field": "name",
        "secondary_field": "description",
        "secondary_default": "''",
        "secondary_type": "TEXT",
        "secondary_json_default": '""',
    }


def _build_models_py(config: dict[str, str]) -> str:
    return f"""TABLE_NAME = "{config["table_name"]}"
RESOURCE_NAME = "{config["resource_name"]}"
RESOURCE_LABEL = "{config["resource_label"]}"
PRIMARY_FIELD = "{config["list_field"]}"
SECONDARY_FIELD = "{config["secondary_field"]}"
"""


def _build_app_py(config: dict[str, str]) -> str:
    table_name = config["table_name"]
    resource_name = config["resource_name"]
    resource_label = config["resource_label"]
    primary_field = config["list_field"]
    secondary_field = config["secondary_field"]
    secondary_type = config["secondary_type"]
    secondary_default = config["secondary_default"]
    secondary_json_default = config["secondary_json_default"]
    list_path = f"/api/{table_name}"
    detail_path = f"/api/{table_name}/<int:item_id>"

    return f"""from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

from models import PRIMARY_FIELD, RESOURCE_LABEL, RESOURCE_NAME, SECONDARY_FIELD, TABLE_NAME


app = Flask(__name__)
CORS(app)

DB_PATH = Path(__file__).resolve().parent / "database.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            \"\"\"
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {primary_field} TEXT NOT NULL,
                {secondary_field} {secondary_type} DEFAULT {secondary_default},
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            \"\"\"
        )
        connection.commit()


def serialize_row(row: sqlite3.Row) -> dict[str, object]:
    return {{
        "id": row["id"],
        PRIMARY_FIELD: row[PRIMARY_FIELD],
        SECONDARY_FIELD: row[SECONDARY_FIELD],
        "createdAt": row["created_at"],
    }}


@app.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {{"status": "ok", "resource": RESOURCE_NAME}}, 200


@app.get("{list_path}")
def list_items() -> tuple[dict[str, object], int]:
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT id, {{PRIMARY_FIELD}}, {{SECONDARY_FIELD}}, created_at FROM {{TABLE_NAME}} ORDER BY id DESC"
        ).fetchall()
    return {{"items": [serialize_row(row) for row in rows]}}, 200


@app.post("{list_path}")
def create_item() -> tuple[dict[str, object], int]:
    payload = request.get_json(silent=True) or {{}}
    primary_value = str(payload.get(PRIMARY_FIELD, "")).strip()
    if not primary_value:
        return {{"error": f"{{PRIMARY_FIELD}} is required"}}, 400
    secondary_value = payload.get(SECONDARY_FIELD, {secondary_json_default})
    with get_connection() as connection:
        cursor = connection.execute(
            f"INSERT INTO {{TABLE_NAME}} ({{PRIMARY_FIELD}}, {{SECONDARY_FIELD}}) VALUES (?, ?)",
            (primary_value, secondary_value),
        )
        item_id = cursor.lastrowid
        connection.commit()
        row = connection.execute(
            f"SELECT id, {{PRIMARY_FIELD}}, {{SECONDARY_FIELD}}, created_at FROM {{TABLE_NAME}} WHERE id = ?",
            (item_id,),
        ).fetchone()
    return {{"item": serialize_row(row), "message": f"{{RESOURCE_LABEL}} created"}}, 201


@app.put("{detail_path}")
def update_item(item_id: int) -> tuple[dict[str, object], int]:
    payload = request.get_json(silent=True) or {{}}
    primary_value = str(payload.get(PRIMARY_FIELD, "")).strip()
    if not primary_value:
        return {{"error": f"{{PRIMARY_FIELD}} is required"}}, 400
    secondary_value = payload.get(SECONDARY_FIELD, {secondary_json_default})
    with get_connection() as connection:
        updated = connection.execute(
            f"UPDATE {{TABLE_NAME}} SET {{PRIMARY_FIELD}} = ?, {{SECONDARY_FIELD}} = ? WHERE id = ?",
            (primary_value, secondary_value, item_id),
        )
        connection.commit()
        if updated.rowcount == 0:
            return {{"error": f"{{RESOURCE_LABEL}} not found"}}, 404
        row = connection.execute(
            f"SELECT id, {{PRIMARY_FIELD}}, {{SECONDARY_FIELD}}, created_at FROM {{TABLE_NAME}} WHERE id = ?",
            (item_id,),
        ).fetchone()
    return {{"item": serialize_row(row), "message": f"{{RESOURCE_LABEL}} updated"}}, 200


@app.delete("{detail_path}")
def delete_item(item_id: int) -> tuple[dict[str, object], int]:
    with get_connection() as connection:
        deleted = connection.execute(f"DELETE FROM {{TABLE_NAME}} WHERE id = ?", (item_id,))
        connection.commit()
    if deleted.rowcount == 0:
        return {{"error": f"{{RESOURCE_LABEL}} not found"}}, 404
    return {{"deleted": True, "id": item_id}}, 200


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=False)
"""


def _build_readme(prompt: str, config: dict[str, str]) -> str:
    table_name = config["table_name"]
    resource_label = config["resource_label"]
    return f"""# Generated Backend App

This backend was generated from the following requirement:

> {prompt.strip() or "Build a CRUD backend service"}

## Stack

- Flask
- SQLite
- Simple CRUD API

## Run

```bash
pip install -r requirements.txt
python backend/app.py
```

## Endpoints

- `GET /health`
- `GET /api/{table_name}`
- `POST /api/{table_name}`
- `PUT /api/{table_name}/<id>`
- `DELETE /api/{table_name}/<id>`

The application creates its SQLite database automatically on first run and exposes a working `{resource_label}` CRUD API.
"""
