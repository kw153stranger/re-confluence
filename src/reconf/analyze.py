"""[Analyze] 로컬 LLM 분류·요약 → analysis JSON (구현설계 §6.2).

raw/*.md 를 읽어 문서별 AnalysisResult 를 생성/저장한다.
멱등: 이미 analysis/<id>.json 이 있으면(resume) 건너뛴다.
"""

from __future__ import annotations

from .config import Config
from .llm import LLMClient, complete_json
from .logging_setup import get_logger, progress
from .markdown import parse_raw
from .models import AnalysisResult, RawDoc
from .prompts import (
    ANALYZE_SYSTEM,
    SUMMARIZE_SYSTEM,
    build_analyze_user,
    build_summarize_user,
)
from .store import Store

log = get_logger("analyze")


def _chunks(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def condense_body(client: LLMClient, doc: RawDoc, chunk_chars: int) -> RawDoc:
    """긴 본문을 청크별로 요약해 통합한다(구현설계 §6.2, 긴 문서 처리)."""
    if len(doc.body_markdown) <= chunk_chars:
        return doc
    parts = _chunks(doc.body_markdown, chunk_chars)
    summaries = [client.chat(SUMMARIZE_SYSTEM, build_summarize_user(p)) for p in parts]
    condensed = "\n".join(summaries)
    log.info("[Analyze] %s 긴 문서 %d청크 → 요약 통합", doc.source_page_id, len(parts))
    return doc.model_copy(update={"body_markdown": condensed})


def analyze_doc(
    client: LLMClient, doc: RawDoc, *, max_retries: int = 3, chunk_chars: int = 8000
) -> AnalysisResult:
    doc = condense_body(client, doc, chunk_chars)
    user = build_analyze_user(doc)
    data = complete_json(client, ANALYZE_SYSTEM, user, max_retries=max_retries)
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
    raw_paths = store.list_raw()
    total = len(raw_paths)
    for idx, raw_path in enumerate(raw_paths, 1):
        progress(log, "Analyze", idx, total)
        doc = parse_raw(raw_path.read_text(encoding="utf-8"))
        out_path = store.analysis_path(doc.source_page_id)
        if resume and store.exists(out_path):
            skipped += 1
            continue
        result = analyze_doc(
            client, doc, max_retries=cfg.llm.max_retries, chunk_chars=cfg.llm.chunk_chars
        )
        results.append(result)
        if not dry_run:
            store.write_json(out_path, result)

    log.info("[Analyze] 분석 %d건, 스킵 %d건", len(results), skipped)
    return results
