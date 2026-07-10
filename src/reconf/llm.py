"""로컬 LLM(OpenAI 호환) 클라이언트 + JSON 강제/검증/재시도 (구현설계 §6.2, §8).

`LLMClient` 프로토콜에 의존하여 analyze 로직을 구현체와 분리한다.
- `OpenAICompatClient`: vLLM/Ollama의 OpenAI 호환 `/chat/completions` 호출.
- 테스트는 동일 프로토콜을 만족하는 fake로 대체한다.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

import httpx

from .logging_setup import get_logger

log = get_logger("llm")


@runtime_checkable
class LLMClient(Protocol):
    def chat(self, system: str, user: str) -> str:
        """system/user 프롬프트로 모델 응답 텍스트를 반환."""
        ...


class OpenAICompatClient:
    """vLLM/Ollama OpenAI 호환 엔드포인트 클라이언트."""

    def __init__(self, endpoint: str, model: str, timeout: float = 120.0):
        self.model = model
        self._client = httpx.Client(base_url=endpoint.rstrip("/"), timeout=timeout)

    def chat(self, system: str, user: str) -> str:
        r = self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def extract_json(text: str) -> dict:
    """모델 응답에서 첫 JSON 객체를 추출한다(코드펜스/잡텍스트 허용)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("응답에서 JSON 객체를 찾지 못했습니다.")
    return json.loads(text[start : end + 1])


def complete_json(client: LLMClient, system: str, user: str, *, max_retries: int = 3) -> dict:
    """JSON 응답을 강제한다. 파싱 실패 시 오류를 되먹여 재요청."""
    prompt = user
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        raw = client.chat(system, prompt)
        try:
            return extract_json(raw)
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            log.warning("[LLM] JSON 파싱 실패 (%d/%d): %s", attempt, max_retries, e)
            prompt = f"{user}\n\n[오류] 유효한 JSON 객체 1개만 출력하세요. 직전 오류: {e}"
    raise ValueError(f"JSON 파싱 {max_retries}회 실패") from last_err
