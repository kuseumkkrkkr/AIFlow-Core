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
| `engine/latex_normalizer.py` | `normalize_latex_input` | 고교 핵심 LaTeX를 안전한 평문 수식으로 정규화 |
| `engine/solver_router.py` | `solve_with_router` | LaTeX 정규화→후보 도구→공통 계산·검산을 조정 |
| `engine/tool_routing.py` | `rank_tools` | rule·neural·embedding의 같은 도구 후보 순위화 |
| `engine/mini_neural_router.py` | `neural_probabilities` | 저장소 가중치의 의존성 없는 소형 MLP 추론 |
| `engine/experiment_runner.py` | `run_experiment` | 실제 전문 로컬 코퍼스의 세 라우터 비교 보고서 |
| `engine/math_tools.py` | `call_math_tool`, `MATH_TOOL_REGISTRY` | 다항식·정수론·로그·지수의 범용 계산 도구 허용 목록·호출 |
| `engine/knowledge_catalog.py` | `load_tool_knowledge_catalogs` | 과목별 카탈로그를 공통 지식 계약으로 정규화 |
| `engine/problem_generation_loop.py` | `generate_and_validate` | 난이도 계약을 포함한 생성 실험 |
| `engine/corpus_runner.py` | `evaluate_records`, `run_corpus` | 코퍼스 회귀 평가 |
| `engine/run_benchmark_matrix.py` | `run_matrix` | 학년·seed 매트릭스 반복 평가 |
| `knowledge/*.json` | JSON 데이터 | 규칙 후보, 개념 그래프, 과목 카탈로그 |
| `tests/*.py` | 테스트 함수 | 규칙·API 직렬화·생성·코퍼스 회귀 검증 |

## 코드 의존 방향

`UI → API → Engine → Knowledge`가 단방향 의존이다. `Knowledge`는 엔진을 import하지 않으며, `tests`와 `docs`는 제품 요청 처리 경로에 포함되지 않는다. 따라서 웹 요청마다 DB 연결이나 전체 코퍼스 스캔이 발생하지 않는다. 미니 신경망 가중치는 요청마다 재학습하지 않고 모듈 캐시로 한 번만 로드한다.

## 확장 규칙

새 수학 지식을 추가할 때는 다음 변경을 한 묶음으로 만든다.

1. `*_tool_catalog.json`에 개념·선수지식·실행 상태를 기록한다.
2. `rule_library.json`에 적용 조건·필수 슬롯·위험도를 기록한다.
3. `tool_routing.py`와 `rule_based_nlp.py`에 후보 분류·최소 근거·슬롯 추출을 추가한다.
4. 계산이 공통화될 수 있으면 `math_tools.py`에 도구와 독립 검산을 추가하고 허용 목록에 등록한다.
5. `tests/test_latex_and_routing.py`와 필요 시 비공개 실제 코퍼스에 정상·거부 사례를 추가한다.
5. 이 Vault의 [[30 Reference/Knowledge Base and Contracts]]를 갱신한다.
