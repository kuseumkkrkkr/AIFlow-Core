---
type: architecture
last_verified: 2026-07-28
sources:
  - ../../../aiflow-core.html
  - ../../../vercel.json
  - ../../../api
  - ../../../engine
  - ../../../knowledge
---

# 시스템 구성도

```mermaid
flowchart LR
    U[사용자 / 브라우저] --> UI[aiflow-core.html<br/>문제 풀이 · 생성 루프 · 알고리즘]
    UI -->|POST /api/solve| SOLVE[api/solve.py]
    UI -->|POST /api/generate| GENAPI[api/generate.py]
    UI -->|POST /api/corpus| CORPUSAPI[api/corpus.py]
    UI -->|GET /api/algorithm| ALGAPI[api/algorithm.py]

    SOLVE --> NLP[engine/rule_based_nlp.py]
    GENAPI --> GEN[engine/problem_generation_loop.py]
    CORPUSAPI --> RUNNER[engine/corpus_runner.py]
    RUNNER --> NLP
    GEN --> NLP

    NLP --> TOOLS[engine/math_tools.py<br/>허용된 수학 도구 호출]
    NLP --> GRAPH[knowledge/concept_graph.json]
    NLP --> RULES[knowledge/rule_library.json]
    ALGAPI --> CATALOG[knowledge/high_school_curriculum_catalog.json]

    GEN --> REPORT[docs/*_validation*.json]
    RUNNER --> REPORT
```

## 레이어별 책임

| 레이어 | 책임 | 상태 변경 |
| --- | --- | --- |
| UI | 문제 입력, API 호출, trace와 검산 표시 | 없음 |
| API | 요청 크기·형식 제한, UTF-8 JSON 응답 | 없음 |
| Engine | 정규화, 분류, 슬롯 추출, 계산, 검산 | 보고서 저장 시에만 파일 생성 |
| Knowledge | 개념·규칙·과목 카탈로그 제공 | 코드 확장 시 갱신 |
| Benchmark | 기대 정답 비교, 결정성 확인 | UTF-8 JSON 보고서 생성 |

## 배포 경계

`vercel.json`이 `/`를 `aiflow-core.html`로, 네 개의 API 경로를 각 Python Vercel 함수로 연결한다. 각 함수의 최대 실행 시간은 10초 또는 30초이며, 외부 DB·외부 LLM 호출은 없다.
