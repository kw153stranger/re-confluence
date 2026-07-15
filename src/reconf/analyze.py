"""[Analyze] 로컬 LLM 분류·요약 → analysis JSON (구현설계 §6.2).

raw/*.md 를 읽어 문서별 AnalysisResult 를 생성/저장한다.
멱등: 이미 analysis/<id>.json 이 있으면(resume) 건너뛴다.
"""

from __future__ import annotations

from . import menu
from .concurrency import run_concurrent
from .config import Config
from .dictionaries import DOMAIN, LIFECYCLE, MENU_TYPE, TECHNOLOGY, snap
from .llm import LLMClient, complete_json
from .logging_setup import ProgressCounter, get_logger
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
    condensed = condense_body(client, doc, chunk_chars)
    user = build_analyze_user(condensed)
    data = complete_json(client, ANALYZE_SYSTEM, user, max_retries=max_retries)
    data["source_page_id"] = doc.source_page_id  # 입력 id로 강제 고정
    result = AnalysisResult.model_validate(data)
    # 사전 스냅(자유 생성 → 표준 값) + 추천 메뉴 경로 (docs/메뉴구조개선방안.md)
    result.domain = snap(result.domain, DOMAIN)
    result.technology = snap(result.technology, TECHNOLOGY)
    result.menu_type = snap(result.menu_type, MENU_TYPE)
    result.lifecycle = snap(result.lifecycle, LIFECYCLE)
    result.menu_path = menu.recommend(result, doc.path)
    return result


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

    raw_paths = store.list_raw()
    counter = ProgressCounter(log, "Analyze", len(raw_paths))

    def work(raw_path) -> tuple[str, AnalysisResult | None]:
        counter.tick()
        doc = parse_raw(raw_path.read_text(encoding="utf-8"))
        out_path = store.analysis_path(doc.source_page_id)
        if resume and store.exists(out_path):
            return ("skip", None)
        try:
            result = analyze_doc(
                client, doc, max_retries=cfg.llm.max_retries, chunk_chars=cfg.llm.chunk_chars
            )
        except Exception as e:  # noqa: BLE001 - 문서 단위 오류 격리
            log.warning("[Analyze] %s 실패: %s", doc.source_page_id, e)
            return ("error", None)
        if not dry_run:
            store.write_json(out_path, result)
        return ("ok", result)

    rows = run_concurrent(work, raw_paths, cfg.concurrency.analyze)
    results = [r for status, r in rows if status == "ok" and r is not None]
    skipped = sum(1 for status, _ in rows if status == "skip")
    errors = sum(1 for status, _ in rows if status == "error")
    log.info("[Analyze] 분석 %d · 스킵 %d · 실패 %d", len(results), skipped, errors)
    return results
