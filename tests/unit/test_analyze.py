"""Analyze 검증 — fake LLMClient + JSON 파싱/재시도."""

import json

import pytest

from reconf import analyze
from reconf.config import Config
from reconf.llm import complete_json, extract_json
from reconf.markdown import dump_raw
from reconf.models import RawDoc
from reconf.store import Store


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def chat(self, system, user):
        self.calls += 1
        return self._responses.pop(0)


VALID = json.dumps(
    {
        "source_page_id": "1",
        "title_normalized": "구매 정산 절차",
        "business": "구매관리",
        "system": "ERP",
        "year": 2024,
        "labels": ["업무/구매관리", "연도/2024"],
        "summary": "정산 절차.",
        "confidence": {"business": 0.9, "project": 0.5, "system": 0.8, "year": 0.99},
    },
    ensure_ascii=False,
)


def test_extract_json_from_noisy_text():
    assert extract_json("설명\n```json\n{\"a\": 1}\n```")["a"] == 1


def test_complete_json_retries_then_succeeds():
    client = FakeLLM(["not json", VALID])
    out = complete_json(client, "sys", "user", max_retries=3)
    assert out["business"] == "구매관리"
    assert client.calls == 2


def test_complete_json_raises_after_max_retries():
    client = FakeLLM(["nope", "still nope", "bad"])
    with pytest.raises(ValueError):
        complete_json(client, "sys", "user", max_retries=3)


def test_analyze_run_writes_analysis(tmp_path):
    store = Store(tmp_path / "vault")
    store.ensure_dirs()
    doc = RawDoc(source_page_id="1", title="구매 정산 절차", body_markdown="정산 절차 본문")
    store.write_raw("1", "구매", dump_raw(doc))

    client = FakeLLM([VALID])
    results = analyze.run(Config(), store, client=client)
    assert len(results) == 1
    assert results[0].business == "구매관리"
    assert store.analysis_path("1").exists()

    # resume: 이미 있으면 스킵
    client2 = FakeLLM([VALID])
    assert analyze.run(Config(), store, resume=True, client=client2) == []
    assert client2.calls == 0
