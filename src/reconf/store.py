"""vault 경로 규칙 · 중간 산출물 읽기/쓰기 (구현설계 §3, §7, §12.6).

M0에서는 파일(file) 백엔드만 제공한다. postgres 백엔드는 M6에서 추가한다.
저장은 문서 단위 UPSERT(= 파일 덮어쓰기)로 멱등하게 이뤄진다.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def content_hash(text: str) -> str:
    """본문 해시 — 임베딩 캐시 무효화 키 (구현설계 §6.3)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Store:
    """vault 디렉토리 구조를 캡슐화한 파일 저장소.

    vault/
      raw/  analysis/  embeddings/  build/
      clusters.json  labels.json  review.json  upload.log
    """

    def __init__(self, vault: str | Path):
        self.root = Path(vault)

    # --- 디렉토리 접근자 ---
    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    @property
    def analysis_dir(self) -> Path:
        return self.root / "analysis"

    @property
    def embeddings_dir(self) -> Path:
        return self.root / "embeddings"

    @property
    def build_dir(self) -> Path:
        return self.root / "build"

    def ensure_dirs(self) -> None:
        for d in (self.raw_dir, self.analysis_dir, self.embeddings_dir, self.build_dir):
            d.mkdir(parents=True, exist_ok=True)

    # --- 저수준 JSON I/O (멱등 UPSERT = 덮어쓰기) ---
    def write_json(self, path: Path, model: BaseModel) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            model.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return path

    def read_json(self, path: Path, model: type[T]) -> T:
        return model.model_validate_json(path.read_text(encoding="utf-8"))

    def exists(self, path: Path) -> bool:
        return path.exists()

    # --- 단계별 경로 헬퍼 ---
    def analysis_path(self, page_id: str) -> Path:
        return self.analysis_dir / f"{page_id}.json"

    def embedding_path(self, page_id: str) -> Path:
        return self.embeddings_dir / f"{page_id}.json"

    @property
    def clusters_path(self) -> Path:
        return self.root / "clusters.json"

    @property
    def labels_path(self) -> Path:
        return self.root / "labels.json"

    @property
    def review_path(self) -> Path:
        return self.root / "review.json"

    # --- raw(Markdown+frontmatter) I/O ---
    def raw_path(self, page_id: str, slug: str) -> Path:
        return self.raw_dir / f"{page_id}__{slug}.md"

    def write_raw(self, page_id: str, slug: str, text: str) -> Path:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        # 같은 page_id의 기존 파일(slug 변경 대비) 제거 후 저장 → 멱등
        for old in self.raw_dir.glob(f"{page_id}__*.md"):
            old.unlink()
        path = self.raw_path(page_id, slug)
        path.write_text(text, encoding="utf-8")
        return path

    def list_raw(self) -> list[Path]:
        return sorted(self.raw_dir.glob("*__*.md"))

    def find_raw(self, page_id: str) -> Path | None:
        matches = list(self.raw_dir.glob(f"{page_id}__*.md"))
        return matches[0] if matches else None

    def list_analysis(self) -> list[Path]:
        return sorted(self.analysis_dir.glob("*.json"))
