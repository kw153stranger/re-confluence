"""FastAPI 백엔드 (구현설계 §12).

파이프라인 코어(reconf.*)를 그대로 재사용하여 CLI와 로직을 공유한다.
- 파이프라인 실행/상태: POST /api/runs, GET /api/runs/{id}
- 검수: GET /api/review/queue, POST /api/review/decisions
- 라벨 거버넌스: POST /api/labels/resolve
- 의미 검색: POST /api/search (pgvector 또는 파일 벡터스토어)

장시간 단계는 실제 배포에서 잡 큐(arq/RQ) 워커로 위임한다. 여기서는 인라인 실행 + 인메모리
런 레지스트리로 계약을 구현한다(§12.1). 문서 본문·임베딩은 사내망 안에서만 처리한다.
"""

from __future__ import annotations

import itertools
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .. import build as build_stage
from .. import review as review_stage
from ..config import Config
from ..embed import Embedder
from ..labels import load_registry, merge_alias, save_registry
from ..models import ReviewDecision, ReviewQueueItem
from ..store import Store
from ..vectorstore import SearchHit, VectorStore, make_vectorstore

# 인라인 실행 가능한 단계(외부 서비스 불필요). 나머지는 워커/설정 필요.
_INLINE_STAGES = {"build", "review", "cluster"}


class RunRequest(BaseModel):
    stage: str
    export_queue: bool = False
    apply: str | None = None


class RunInfo(BaseModel):
    id: int
    stage: str
    status: str  # queued | running | done | failed
    detail: str = ""


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    business: str | None = None
    year: int | None = None


class LabelResolveRequest(BaseModel):
    namespace: str
    canonical: str
    alias: str


def create_app(
    store: Store,
    cfg: Config | None = None,
    *,
    embedder: Embedder | None = None,
    vectorstore: VectorStore | None = None,
) -> FastAPI:
    cfg = cfg or Config()
    app = FastAPI(title="Confluence AI 재구성 — 웹서비스", version="0.1.0")
    runs: dict[int, RunInfo] = {}
    counter = itertools.count(1)

    def _get_vs() -> VectorStore:
        return vectorstore or make_vectorstore(cfg, store)

    def _get_embedder() -> Embedder:
        if embedder is not None:
            return embedder
        from ..embed import TEIEmbedder

        return TEIEmbedder(cfg.embeddings)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "vault": str(store.root), "db_backend": cfg.db.backend}

    @app.get("/api/review/queue", response_model=list[ReviewQueueItem])
    def review_queue() -> list[ReviewQueueItem]:
        return review_stage.load_queue(store)

    @app.post("/api/review/decisions")
    def review_decisions(decisions: list[ReviewDecision]) -> dict[str, int]:
        review_stage.apply_decisions(store, decisions)
        approved = sum(1 for d in decisions if d.status == "approved")
        return {"applied": len(decisions), "approved": approved}

    @app.post("/api/labels/resolve")
    def labels_resolve(req: LabelResolveRequest) -> dict[str, str]:
        reg = load_registry(store)
        merge_alias(reg, req.namespace, req.canonical, req.alias)
        save_registry(store, reg)
        return {"canonical": f"{req.namespace}/{req.canonical}", "merged": req.alias}

    @app.post("/api/search", response_model=list[SearchHit])
    def search(req: SearchRequest) -> list[SearchHit]:
        vector = _get_embedder().embed([req.query])[0]
        return _get_vs().search(vector, req.top_k, req.business, req.year)

    @app.post("/api/runs", response_model=RunInfo)
    def create_run(req: RunRequest) -> RunInfo:
        run = RunInfo(id=next(counter), stage=req.stage, status="running")
        runs[run.id] = run
        try:
            if req.stage == "build":
                pages = build_stage.run(cfg, store)
                run.detail = f"pages={len(pages)}"
            elif req.stage == "review":
                review_stage.run(cfg, store, export_queue=req.export_queue, apply=req.apply)
                run.detail = "review 반영"
            else:
                # export/analyze/cluster/upload 등은 워커·클라이언트 설정 필요
                raise RuntimeError(f"'{req.stage}' 단계는 워커/서비스 설정이 필요합니다.")
            run.status = "done"
        except Exception as e:  # noqa: BLE001 - 상태로 표면화
            run.status = "failed"
            run.detail = str(e)
        return run

    @app.get("/api/runs/{run_id}", response_model=RunInfo)
    def get_run(run_id: int) -> RunInfo:
        if run_id not in runs:
            raise HTTPException(status_code=404, detail="run not found")
        return runs[run_id]

    return app
