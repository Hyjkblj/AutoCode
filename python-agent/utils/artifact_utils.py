from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class ArtifactBundle:
    artifact_id: str
    file_path: Path
    file_name: str
    sha256: str
    size_bytes: int
    mime_type: str
    artifact_type: str

    def to_event_payload(self) -> dict[str, object]:
        return {
            "artifact": {
                "artifactId": self.artifact_id,
                "type": self.artifact_type,
                "name": self.file_name,
                "hash": f"sha256:{self.sha256}",
                "size": self.size_bytes,
                "mime": self.mime_type,
            },
            "kind": self.artifact_type,
        }


def build_export_zip(workspace: Path, relative_files: Sequence[str], *, file_name: str = "export.zip") -> ArtifactBundle:
    if not relative_files:
        raise ValueError("relative_files must not be empty")

    workspace_root = workspace.resolve(strict=False)
    output_path = workspace_root / file_name
    normalized_files: list[str] = []
    for rel in relative_files:
        cleaned = str(rel).strip().replace("\\", "/")
        if not cleaned:
            continue
        absolute = (workspace_root / cleaned).resolve(strict=False)
        if not absolute.exists() or not absolute.is_file():
            raise FileNotFoundError(f"artifact source file not found: {cleaned}")
        normalized_files.append(cleaned)

    if not normalized_files:
        raise ValueError("no valid files to package")

    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for rel in sorted(set(normalized_files)):
            zipf.write((workspace_root / rel).resolve(strict=False), arcname=rel)

    size_bytes = output_path.stat().st_size
    sha = _sha256_file(output_path)
    artifact_id = f"art_zip_{sha[:12]}"
    return ArtifactBundle(
        artifact_id=artifact_id,
        file_path=output_path,
        file_name=file_name,
        sha256=sha,
        size_bytes=size_bytes,
        mime_type="application/zip",
        artifact_type="zip",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 64), b""):
            digest.update(chunk)
    return digest.hexdigest()
