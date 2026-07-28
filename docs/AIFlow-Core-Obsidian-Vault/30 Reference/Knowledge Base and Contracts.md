---
type: reference
last_verified: 2026-07-28
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
| `high_school_curriculum_catalog.json` | 수학Ⅰ·수학Ⅱ·미적분·확통·기하 확장 목록 | `/api/algorithm` |
| `validation_contract.json` | PASS/FAIL 관련 기준 | 연구·문서 기준 |

## 실행 가능 범위

현재 카탈로그의 모든 항목이 자동 풀이되는 것은 아니다. `execution_status`와 `rule_ids`가 적힌 항목은 관련 실행 규칙이 있으며, 그 외 항목은 검색·확장 우선순위를 위한 지식이다.

대표 실행 규칙:

- 수열: 등차수열, 등비수열 일반항·합
- 수학Ⅰ: 지수·로그, 특수각 삼각함수, 함수·합성·역함수
- 수학Ⅱ: 다항식 극한, 거듭제곱 미분·접선·정적분
- 미적분: `sin`, `cos` 미분값
- 확률과 통계: 조합·순열·조건부확률·이항분포 점확률
- 기하: 기본 도형, 평면벡터 성분 내적

대표 도구 호출: 두 일차식 나머지 보간, 유리함수 구간 극값, 양의 정수 미지수를 포함한 2×2 행렬 곱이다. 도구는 추출된 슬롯만 받고, 등록되지 않은 도구 ID 호출과 임의 코드 실행을 허용하지 않는다.

## PASS 조건

1. 요구 슬롯이 모두 추출된다.
2. 도메인 제약(예: 확률 범위, 정수근, 벡터 성분)이 유효하다.
3. 계산 결과가 독립 `verify_result` 불변식을 만족한다.
4. 생성·코퍼스 모드에서는 기대 정답도 일치한다.

이 중 하나라도 실패하면 `PASS`가 아니라 `FAIL`과 이유를 반환한다.
