---
type: reference
last_verified: 2026-07-29
sources:
  - ../../../knowledge/concept_graph.json
  - ../../../knowledge/rule_library.json
  - ../../../knowledge/high_school_curriculum_catalog.json
  - ../../../engine/problem_generation_loop.py
---

# 지식 베이스·계약

## 지식 파일 역할

| 파일 | 내용 | 런타임 소비자 |
| --- | --- | --- |
| `concept_graph.json` | 개념 노드, 토픽, 선수 관계 | `classify` |
| `rule_library.json` | 규칙 ID, 적용 조건, 필수 슬롯, 위험도 | `classify`, `select_optimal_rule` |
| `high_school_curriculum_catalog.json` | 수학 상·하 호환 관계와 수학Ⅰ·수학Ⅱ·미적분·확통·기하 확장 목록 | `/api/algorithm` |
| `geometry_gui_tool_catalog.json` | 좌표 GUI의 거리·중점·넓이·벡터 내적·직선 교점 계약 | `/api/algorithm`, `geometry_gui` |
| `*_tool_catalog.json` | 과목별 개념, 입력 슬롯, 도구, 공식, 검산 불변식 | `/api/algorithm`, 지식 확장 설계 |
| `validation_contract.json` | PASS/FAIL 관련 기준 | 연구·문서 기준 |

## 실행 가능 범위

현재 카탈로그의 모든 항목이 자동 풀이되는 것은 아니다. `execution_status`와 `rule_ids`가 적힌 항목은 관련 실행 규칙이 있으며, 그 외 항목은 검색·확장 우선순위를 위한 지식이다.

대표 실행 규칙:

- 수열: 등차수열, 등비수열 일반항·합
- 수학Ⅰ: 지수·로그, 특수각 삼각함수, 함수·합성·역함수
- 수학Ⅱ: 다항식 극한, 거듭제곱 미분·접선·정적분
- 미적분: `sin`, `cos` 미분값
- 확률과 통계: 조합·순열·조건부확률·이항분포 점확률
- 기하: 기본 도형, 평면벡터 성분 내적, 좌표 GUI 거리·중점·삼각형 넓이·벡터 내적·두 직선 교점

대표 도구 호출: 두 일차식 나머지 보간, 유리함수 구간 극값, 양의 정수 미지수를 포함한 2×2 행렬 곱, Horner 다항식 값, 최대공약수, 로그 곱 방정식, 지수함수 점근선 거리, 로그함수 역함수의 거듭제곱 좌표, 일차식 절댓값 방정식의 두 분기 해다. 도구는 추출된 슬롯만 받고, 등록되지 않은 도구 ID 호출과 임의 코드 실행을 허용하지 않는다.

각 과목 도구 카탈로그는 `concept_id`, `required_slots`, `tool`, `formula`, `verification_invariant`, `supported_example`, `unsupported_boundary`를 가진다. 이 형식은 키워드 나열이 아니라 새 파서·도구·검산 규칙을 추가하기 위한 구현 계약이다.

예를 들어 `fn_ineq_absolute_value_equation_linear`은 `a,b,target` 슬롯만 `solve_absolute_linear_equation`에 전달한다. 도구는 `ax+b=target`과 `ax+b=-target`을 각각 풀고, 반환한 모든 해를 원래 절댓값식에 재대입한다. `target<0`, `a=0`, 이차 이상 내부식, 양변 절댓값은 `PASS`하지 않는다. 이 구조는 `|ax+b|=c`를 보통 일차방정식으로 오인해 한 해만 반환하는 허위 PASS도 차단한다.

`fn_ineq_linear_inequality_solution_set`은 `a,b,relation,c` 슬롯을 `solve_linear_inequality`에 전달한다. 경계 `(c-b)/a`를 계산하고, `a<0`일 때만 비교 기호를 뒤집는다. 경계와 양쪽 표본을 원부등식에 다시 대입해 해집합 방향과 경계 포함 여부를 검산한다. 비교 기호가 있는 입력은 등식용 `cm_linear` 도구가 실행하지 않아 경계값 하나를 정답처럼 보고하지 않는다. 단, 비교 조건이 둘 이상인 함수·최적화 문항과 연쇄 구간은 이 단일 계약의 적용 전제가 아니므로 `FAIL`로 남긴다.

현재 과목별 카탈로그는 기존 170개에 1차 대학 기초수학(선형대수 33개, 기초해석 32개, 이산수학 28개), 2차 확장(정수론·추상대수 30개, 수치해석·최적화 32개, 고급기하 28개), 3차 확장(확률·통계 27개, 미분방정식 32개, 복소해석 30개), 실제 고2 기출에서 승격한 로그함수 구간 극값·특수각 사인 구간방정식·다항식 동류항 덧셈, 좌표 GUI 기하 5개 계약을 더해 총 450개 항목이다. 새 항목은 `prerequisite_ids`로 선수 지식 그래프를 표현한다. `engine/knowledge_catalog.py`가 과거 `items`·`concepts`, 단수·복수 검산 필드 차이를 공통 스키마로 정규화하고, `tests/test_knowledge_catalog.py`가 항목 수·ID 중복·필수 필드·선수관계 존재·순환·실행 항목의 실제 rule/math-tool 참조를 검증한다.

## PASS 조건

1. 요구 슬롯이 모두 추출된다.
2. 도메인 제약(예: 확률 범위, 정수근, 벡터 성분)이 유효하다.
3. 계산 결과가 독립 `verify_result` 불변식을 만족한다.
4. 생성·코퍼스 모드에서는 기대 정답도 일치한다.

이 중 하나라도 실패하면 `PASS`가 아니라 `FAIL`과 이유를 반환한다.
