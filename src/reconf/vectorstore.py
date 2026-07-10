"""벡터 스토어 추상화 (구현설계 §12.2).

- `VectorStore` 프로토콜: upsert / search(코사인 근접 + 메타 필터).
- `FileVectorStore`: vault의 embeddings/*.json + analysis 메타로 인메모리 검색(셀프호스트·기본).
- `PgVectorStore`: Postgres + pgvector 구현(psycopg). 실 배포용.

의미 검색은 쿼리 임베딩(TEI)을 받아 저장 벡터와 코사인 근접을 계산한다.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel

from .markdown import parse_raw
from .models import AnalysisResult, EmbeddingRecord
from .store import Store


class SearchHit(BaseModel):
    source_page_id: str
    score: float
    title: str = ""
    business: str | None = None
    year: int | None = None


@runtime_checkable
class VectorStore(Protocol):
    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        business: str | None = None,
        year: int | None = None,
    ) -> list[SearchHit]:
        ...


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return 0.0 if na == 0 or nb == 0 else float(np.dot(a, b) / (na * nb))


class FileVectorStore:
    """vault 파일 기반 벡터 검색(셀프호스트 기본). 대규모는 PgVectorStore 권장."""

    def __init__(self, store: Store):
        self.store = store

    def _load(self) -> list[tuple[EmbeddingRecord, AnalysisResult | None, str]]:
        analyses = {
            p.stem: self.store.read_json(p, AnalysisResult) for p in self.store.list_analysis()
        }
        titles: dict[str, str] = {}
        for p in self.store.list_raw():
            d = parse_raw(p.read_text(encoding="utf-8"))
            titles[d.source_page_id] = d.title
        rows = []
        for p in self.store.embeddings_dir.glob("*.json"):
            rec = self.store.read_json(p, EmbeddingRecord)
            a = analyses.get(rec.source_page_id)
            rows.append((rec, a, titles.get(rec.source_page_id, "")))
        return rows

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        business: str | None = None,
        year: int | None = None,
    ) -> list[SearchHit]:
        q = np.array(query_vector, dtype=float)
        hits: list[SearchHit] = []
        for rec, a, title in self._load():
            if business and (a is None or a.business != business):
                continue
            if year is not None and (a is None or a.year != year):
                continue
            hits.append(
                SearchHit(
                    source_page_id=rec.source_page_id,
                    score=round(_cosine(q, np.array(rec.vector, dtype=float)), 4),
                    title=title,
                    business=a.business if a else None,
                    year=a.year if a else None,
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]


class PgVectorStore:
    """Postgres + pgvector 구현 (실 배포용). psycopg 필요.

    스키마는 migrations/001_init.sql 참고. 인메모리 없이 DB에서 ANN 검색한다.
    """

    def __init__(self, dsn: str):
        import psycopg  # 지연 import (optional dep)

        self._conn = psycopg.connect(dsn)

    def upsert(self, rec: EmbeddingRecord, business: str | None, year: int | None, title: str):
        with self._conn.cursor() as cur:
            cur.execute(
                """
                insert into doc_embeddings
                    (source_page_id, model, dim, content_hash, business, year, title, embedding)
                values (%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (source_page_id) do update set
                    model=excluded.model, dim=excluded.dim, content_hash=excluded.content_hash,
                    business=excluded.business, year=excluded.year, title=excluded.title,
                    embedding=excluded.embedding
                """,
                (rec.source_page_id, rec.model, rec.dim, rec.content_hash,
                 business, year, title, rec.vector),
            )
        self._conn.commit()

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        business: str | None = None,
        year: int | None = None,
    ) -> list[SearchHit]:
        where, params = [], [query_vector]
        if business:
            where.append("business = %s")
            params.append(business)
        if year is not None:
            where.append("year = %s")
            params.append(year)
        clause = ("where " + " and ".join(where)) if where else ""
        params.append(top_k)
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                select source_page_id, title, business, year,
                       1 - (embedding <=> %s) as score
                from doc_embeddings {clause}
                order by embedding <=> %s limit %s
                """,
                [query_vector, *params[1:-1], query_vector, top_k],
            )
            return [
                SearchHit(
                    source_page_id=r[0], title=r[1], business=r[2], year=r[3], score=float(r[4])
                )
                for r in cur.fetchall()
            ]


def make_vectorstore(cfg, store: Store) -> VectorStore:
    if cfg.db.backend == "postgres":
        return PgVectorStore(cfg.db.dsn)
    return FileVectorStore(store)
