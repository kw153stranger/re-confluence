"""[Analyze] 로컬 LLM 분류·요약 → analysis JSON (구현설계 §6.2).

raw/*.md 를 읽어 문서별 AnalysisResult 를 생성/저장한다.
멱등: 이미 analysis/<id>.json 이 있으면(resume) 건너뛴다.
"""

from __future__ import annotations

from .config import Config
from .llm import LLMClient, complete_json
from .logging_setup import get_logger
from .markdown import parse_raw
from .models import AnalysisResult
from .prompts import ANALYZE_SYSTEM, build_analyze_user
from .store import Store

log = get_logger("analyze")


def analyze_doc(client: LLMClient, doc, *, max_retries: int = 3) -> AnalysisResult:
    user = build_analyze_user(doc)
    data = complete_json(client, ANALYZE_SYSTEM, user, max_retries=max_retries)
    data.setdefault("source_page_id", doc.source_page_id)
    data["source_page_id"] = doc.source_page_id  # 입력 id로 강제 고정
    return AnalysisResult.model_validate(data)


def run(
    cfg: Config,
    store: Store,
    *,
    resume: bool = False,
    dry_run: bool = False,
    client: LLMClient | None = None,
) -> list[AnalysisResult]:
    store.ensure_dirs()
    if client is None:
        from .llm import OpenAICompatClient

        client = OpenAICompatClient(cfg.llm.endpoint, cfg.llm.model)

    results: list[AnalysisResult] = []
    skipped = 0
    for raw_path in store.list_raw():
        doc = parse_raw(raw_path.read_text(encoding="utf-8"))
        out_path = store.analysis_path(doc.source_page_id)
        if resume and store.exists(out_path):
            skipped += 1
            continue
        result = analyze_doc(client, doc, max_retries=cfg.llm.max_retries)
        results.append(result)
        if not dry_run:
            store.write_json(out_path, result)
        log.info("[Analyze] %s → %s (conf.business=%.2f)",
                 doc.source_page_id, result.business, result.confidence.business)

    log.info("[Analyze] 분석 %d건, 스킵 %d건", len(results), skipped)
    return results
