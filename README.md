# Confluence AI 재구성 (Confluence AI Restructure)

흩어진 Confluence 문서를 **MCP**로 수집하고 **로컬 LLM(Qwen3-30B-A3B)** 으로 분석해,
**업무 중심 정보구조(IA)** 로 재구성한 뒤 신규 Confluence 공간에 반영하는 프로젝트입니다.

> 현재 단계(M1): **기획문서 + 화면 목업**. 파이프라인 실제 구현은 후속 단계(M2~).

## 산출물 (Deliverables)

| 산출물 | 경로 | 설명 |
| --- | --- | --- |
| 📄 기획문서 | [`docs/기획서.md`](docs/기획서.md) | v3.1 상세 기획서 (아키텍처·IA·라벨 표준·로드맵) |
| 🏗️ 구현 설계서 | [`docs/구현설계.md`](docs/구현설계.md) | Python 기준 기술 설계 (스택·구조·모델·CLI·단계별 설계·테스트) |
| ✅ 실행 태스크 | [`docs/실행태스크.md`](docs/실행태스크.md) | 마일스톤별 체크리스트 + 수용기준(DoD) (M0~M5) |
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
