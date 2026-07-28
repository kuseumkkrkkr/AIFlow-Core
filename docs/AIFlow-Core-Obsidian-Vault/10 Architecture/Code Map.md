---
type: reference
last_verified: 2026-07-28
---

# 코드 구성표

| 경로 | 진입점·핵심 함수 | 역할 |
| --- | --- | --- |
| `aiflow-core.html` | `solve`, `generate`, `loadAlgorithm` | 단일 페이지 UI와 API 연결 |
| `api/solve.py` | `handler.do_POST` | 문제 한 개를 전체 엔진으로 풀이 |
| `api/generate.py` | `handler.do_POST` | 난이도·seed 기반 생성과 검증 실행 |
| `api/corpus.py` | `handler.do_POST` | 최대 100개 사용자 문항을 일괄 채점 |
| `api/algorithm.py` | `ALGORITHM` | 웹에 알고리즘·지식 카탈로그 공개 |
| `engine/rule_based_nlp.py` | `classify`, `solve_rule`, `verify_result` | 엔진의 핵심 해석·계산·검산 |
| `engine/math_tools.py` | `call_math_tool`, `MATH_TOOL_REGISTRY` | 범용 수학 계산 도구의 허용 목록·호출 |
| `engine/problem_generation_loop.py` | `generate_and_validate` | 난이도 계약을 포함한 생성 실험 |
| `engine/corpus_runner.py` | `evaluate_records`, `run_corpus` | 코퍼스 회귀 평가 |
| `engine/run_benchmark_matrix.py` | `run_matrix` | 학년·seed 매트릭스 반복 평가 |
| `knowledge/*.json` | JSON 데이터 | 규칙 후보, 개념 그래프, 과목 카탈로그 |
| `tests/*.py` | 테스트 함수 | 규칙·API 직렬화·생성·코퍼스 회귀 검증 |

## 코드 의존 방향

`UI → API → Engine → Knowledge`가 단방향 의존이다. `Knowledge`는 엔진을 import하지 않으며, `tests`와 `docs`는 제품 요청 처리 경로에 포함되지 않는다. 따라서 웹 요청마다 DB 연결이나 전체 코퍼스 스캔이 발생하지 않는다.

## 확장 규칙

새 수학 지식을 추가할 때는 다음 변경을 한 묶음으로 만든다.

1. `high_school_curriculum_catalog.json`에 개념과 실행 상태를 기록한다.
2. `rule_library.json`에 적용 조건·필수 슬롯·위험도를 기록한다.
3. `rule_based_nlp.py`에 분류, 슬롯 추출, 계산, 독립 검산을 추가한다.
4. `tests/test_rule_based_nlp.py`와 필요 시 코퍼스 fixture에 정상·거부 사례를 추가한다.
5. 이 Vault의 [[30 Reference/Knowledge Base and Contracts]]를 갱신한다.
