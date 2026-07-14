# Confluence AI 재구성 (Confluence AI Restructure)

흩어진 Confluence 문서를 **MCP**로 수집하고 **로컬 LLM(Qwen3-30B-A3B)** 으로 분석해,
**업무 중심 정보구조(IA)** 로 재구성한 뒤 신규 Confluence 공간에 반영하는 프로젝트입니다.

> 진행: **배치 파이프라인(M0~M4) + 웹서비스·벡터DB(M6) 로직 구현+테스트 완료**.
> Export→Analyze→Cluster→Build→Review→Upload + FastAPI(검수·의미검색·오케스트레이션). 47 tests.
> 실 서비스 스모크·pgvector 실적재·프런트·M5(하드닝)는 후속.
> 단계별 점검 항목: [`docs/단계별점검리스트.md`](docs/단계별점검리스트.md).
>
> 🚀 **처음 받는다면 → [로컬 실행 가이드](docs/로컬실행가이드.md)** (클론·설치·실행·트러블슈팅).

## 산출물 (Deliverables)

| 산출물 | 경로 | 설명 |
| --- | --- | --- |
| 🚀 로컬 실행 가이드 | [`docs/로컬실행가이드.md`](docs/로컬실행가이드.md) | 클론·설치·파이프라인/웹 실행·트러블슈팅 (처음이라면 여기부터) |
| 📄 기획문서 | [`docs/기획서.md`](docs/기획서.md) | v3.1 상세 기획서 (아키텍처·IA·라벨 표준·로드맵) |
| 🏗️ 구현 설계서 | [`docs/구현설계.md`](docs/구현설계.md) | Python 기준 기술 설계 (스택·구조·모델·CLI·단계별 설계·테스트) |
| ✅ 실행 태스크 | [`docs/실행태스크.md`](docs/실행태스크.md) | 마일스톤별 체크리스트 + 수용기준(DoD) (M0~M6) |
| 🔎 단계별 점검 | [`docs/단계별점검리스트.md`](docs/단계별점검리스트.md) | 각 단계 실행 후 점검 항목·확인 방법·대응 |
| 🆔 페이지 ID 관리 | [`docs/페이지ID관리.md`](docs/페이지ID관리.md) | 원본↔신규 ID 연결·멱등 업로드(신규/업데이트 구분) |
| 🧩 코어 코드 | [`src/reconf/`](src/reconf) | `reconf` CLI 6단계 파이프라인·모델·설정·저장소 |
| 🌐 웹서비스·벡터DB | [`src/reconf/web/`](src/reconf/web) · [`migrations/`](migrations) | FastAPI(검수·검색·오케스트레이션) + pgvector 스키마 (M6) |
| 🅜 목업 허브 | [`mockups/index.html`](mockups/index.html) | 3개 목업으로 이동하는 시작 페이지 |
| ① 신규 공간 화면 | [`mockups/confluence-space.html`](mockups/confluence-space.html) | Page Tree · Page Properties · Report · Content by Label |
| ② 파이프라인/검수 | [`mockups/pipeline-dashboard.html`](mockups/pipeline-dashboard.html) | 6단계 진행 + 사람 검수(Review) UI |
| ③ AI 분류(JSON) 뷰 | [`mockups/analysis-json.html`](mockups/analysis-json.html) | 원본↔JSON 대조 · 신뢰도 · 클러스터링 |

## 목업 열람 방법

각 HTML은 **외부 의존성이 없는 자체 완결형** 파일입니다. 브라우저로 직접 열면 됩니다.

```bash
# macOS
open mockups/index.html
# Linux
xdg-open mockups/index.html
```

- 라이트/다크 모드 모두 대응하며, 각 화면 상단 **🌗 테마** 버튼으로 전환할 수 있습니다.
- `mockups/index.html`에서 시작해 3개 화면을 둘러보세요.

## 개발 (Development)

`reconf` CLI 파이프라인의 코드는 `src/reconf/`에 있습니다 (Python 3.11+).

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"          # 패키지 + 개발 의존성(pytest, ruff)

reconf --help                    # 서브커맨드 확인
reconf export --vault ./vault    # 단계 실행 (실 수집은 CONFLUENCE_* 환경변수 필요)

ruff check .                     # lint
pytest -q                        # 테스트 (47 passed)
```

- 설정은 `config.example.yaml`을 복사해 `config.yaml`로 사용 (`--config` 옵션).
- 비밀값(Confluence 토큰 등)은 파일이 아닌 **환경변수**로 주입합니다.
- 각 단계는 독립 실행되며 중간 산출물을 `vault/`에 저장합니다. 상세: [`docs/구현설계.md`](docs/구현설계.md).

### 웹서비스 (M6)

```bash
pip install -e ".[web]"          # FastAPI + uvicorn
reconf serve --vault ./vault     # http://127.0.0.1:8000
```

- API: `POST /api/runs`·`GET /api/runs/{id}`(오케스트레이션), `GET /api/review/queue`·
  `POST /api/review/decisions`(검수), `POST /api/labels/resolve`(라벨 거버넌스), `POST /api/search`(의미 검색).
- 벡터DB: 기본은 파일 기반(`FileVectorStore`). Postgres/pgvector는 `pip install -e ".[postgres]"` +
  `migrations/001_init.sql` 적용 후 `config.db.backend=postgres`. 상세: [`docs/구현설계.md`](docs/구현설계.md) §12.

## 파이프라인 6단계 (요약)

```
Export → Analyze → Cluster → Build → Review → Upload
```

| 단계 | 역할 | 산출물 |
| --- | --- | --- |
| **Export** | mcp-atlassian으로 페이지·첨부 수집 | `vault/raw/*.md` |
| **Analyze** | Qwen3-30B-A3B 분류·요약 (JSON) | `vault/analysis/*.json` |
| **Cluster** | 동일 업무 병합·연도 그룹핑·중복 탐지 | `vault/clusters.json` |
| **Build** | 업무 중심 Page Tree·Properties·Labels 생성 | `vault/build/` |
| **Review** | 사람 검수 (분류 확인·수정·승인) | `vault/review.json` |
| **Upload** | 신규 Space 생성·업로드 (멱등) | 신규 Confluence Space |

- 각 단계는 **독립 실행** 가능하고, 중간 산출물을 파일로 남겨 **재현·재실행**을 보장합니다.
- 원본 Space는 **읽기 전용**으로 보존하며, 로컬 LLM 사용으로 문서를 외부로 전송하지 않습니다.

자세한 설계는 [`docs/기획서.md`](docs/기획서.md)를 참고하세요.
