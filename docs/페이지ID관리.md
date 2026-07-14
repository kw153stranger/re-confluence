# 페이지 ID 관리 · 멱등 업로드 (Page ID & Idempotency)

> 원본 페이지 ID와 신규 Space의 페이지 ID가 어떻게 연결되고, 재업로드 시 신규 생성/업데이트를
> 어떻게 구분하는지 설명한다. (구현: `src/reconf/confluence.py`, `src/reconf/upload.py`)

## 1. 두 가지 ID

| 구분 | 무엇 | 어디서 |
| --- | --- | --- |
| **source_page_id** | 원본 Confluence 페이지 ID | Export가 수집. Export/Analyze/Cluster/Build/Review까지 이 키로만 다룸 |
| **target_page_id** | 신규 Space에 생성된 페이지 ID | Upload 시 Confluence가 **새로 발급** |

Export→…→Build 단계는 **원본 ID(source_page_id)만** 사용한다. 신규 ID는 Upload 시점에 생긴다.

## 2. 원본↔신규 연결 = "src-<id>" 라벨

신규 페이지를 만들 때, 그 페이지에 **`src-<source_page_id>` 라벨**을 부착한다.
이 라벨이 원본과 신규 페이지를 잇는 **멱등 키**다. (별도 로컬 매핑 파일을 두지 않는다.)

```
원본 123456  ──Upload──▶  신규 페이지(target_page_id) + 라벨 "src-123456"
```

## 3. 신규 / 업데이트 구분 흐름

Upload는 **대상 Space를 CQL로 조회**해서 판단한다 (`_find_by_source`).

```
upsert_page(space, source_page_id, ...):
  1) CQL 조회:  space = "<대상>" AND label = "src-<source_page_id>"   (expand=version)
  2) 결과 없음  → CREATE:  POST /content  → 새 target_page_id 발급
                          → POST /content/{id}/label 로 "src-<id>" + 표준 라벨 부착
  3) 결과 있음  → UPDATE:  PUT /content/{id}  (version.number = 현재+1)
```

- **"로컬에 없으면 신규 업로드, 있으면 업데이트"** 를 원격 Confluence 라벨 존재 여부로 판단한다.
  즉 판단 근거는 **로컬 상태가 아니라 대상 Space의 라벨**이다.
- `upload.log` 에 `source_page_id → target_page_id` 매핑이 기록되지만, 이는 **감사/추적용**이며
  신규/업데이트 결정에는 사용하지 않는다.

### PUT 업데이트와 version 필드 (중요)
Confluence 업데이트(PUT)는 **`version.number` 증가가 필수**다. `_find_by_source`가 조회 시
`expand=version`으로 현재 버전을 함께 읽고, PUT payload에 `version = {number: 현재+1}`을 넣는다.
(누락 시 실 서버에서 409 Conflict.)

## 4. 구조 페이지도 동일 규약

IA 계층의 합성 페이지(업무/개요/작업실적/연도)도 같은 upsert를 쓴다. 멱등 키는 합성 키다.

| 페이지 | 멱등 키(source_page_id 위치) |
| --- | --- |
| 업무 | `biz-<업무>` |
| 개요 | `overview-<업무>` |
| 작업실적 | `worklog-<업무>` |
| 연도 | `year-<업무>-<연도>` |
| 문서 | 원본 `source_page_id`(숫자) |

## 5. 재현성·재실행

- 같은 입력으로 Upload를 **다시 실행하면 중복 페이지가 생기지 않는다** — 라벨 조회로 기존을 찾아 갱신.
- 부분 실패는 격리되어 `upload.log`에 남고, 재실행 시 성공분은 그대로 갱신(멱등)된다.

## 6. 제약 · 주의 (현행 라벨 방식)

- **Confluence 라벨은 공백/일부 특수문자를 허용하지 않는다.** 문서 멱등 키는 숫자 ID라 안전하지만,
  구조 페이지 키에 공백이 있는 업무명(예: `biz-SSL 적용`)은 실 Confluence에서 라벨화가 제한될 수 있다.
  → 실 배포 시 구조 키를 슬러그화(공백 제거)하거나 라벨 대신 페이지 프로퍼티/local 매핑으로 보강하는 것을 권장.
- 매 페이지마다 CQL 조회가 1회 발생한다(대량 업로드 시 호출량 고려).

> 대안(로컬 매핑 `upload_map.json` 등)은 채택하지 않고 **현행 라벨 조회 방식을 유지**한다.
> 관련 구현: `ConfluenceRestWriter._find_by_source` / `.upsert_page` (`src/reconf/confluence.py`).
