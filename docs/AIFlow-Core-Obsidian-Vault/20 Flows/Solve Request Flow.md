---
type: flow
last_verified: 2026-07-28
sources:
  - ../../../api/solve.py
  - ../../../engine/rule_based_nlp.py
  - ../../../engine/latex_normalizer.py
  - ../../../engine/solver_router.py
---

# 문제 풀이 플로우

```mermaid
flowchart TD
    A[문제 문자열] --> B{크기 1~200,000 bytes?}
    B -- 아니오 --> R400[HTTP 413 FAIL]
    B -- 예 --> C[UTF-8 JSON decode]
    C --> D[LaTeX·문자 정규화<br/>미지원 명령은 FAIL]
    D --> E[router 선택<br/>rule · mini neural · embedding]
    E --> F[후보 도구 순위화]
    F --> G[parse_for_domain<br/>후보별 계수·항·조건 슬롯 추출]
    G --> H[solve_rule / call_math_tool]
    H --> I{규칙의 입력 조건 충족?}
    I -- 아니오 --> J[FAIL + reason]
    I -- 예 --> K[verify_result<br/>독립 불변식 재계산]
    K --> L{검산 통과?}
    L -- 아니오 --> J
    L -- 예 --> M[build_solution_trace]
    M --> N[UTF-8 JSON PASS 응답]
```

## 응답 계약

`/api/solve`에는 `router`를 `rule`(기본), `neural`, `embedding`으로 줄 수 있다. 응답은 `status`, `normalized_question`, `router`, `candidates`, `attempts`, `parse`, `result`, `steps`, `summary`를 갖는다.

- `router`: 선택 방식·모델 버전·최종 도구 도메인·점수
- `candidates`와 `attempts`: 후보 순서와 각 후보의 슬롯·실행 결과
- `parse`: 원문·정규화 문장·LaTeX 정규화 결과·도메인·슬롯
- `result`: 정답, 공식, 검산 결과 또는 실패 이유
- `steps`: 학생에게 보여 줄 순서형 풀이

`Fraction`처럼 기본 JSON이 표현하지 못하는 수학 객체는 정확한 문자열(예: `"1/2"`)로 보존한다.

## 예시: 이항분포

`이항분포 n=5, p=1/2에서 X=2일 확률`은 `stat_binomial_distribution`으로 분류된다. 슬롯 `n=5, p=1/2, k=2`를 추출한 뒤 `nCk·p^k·(1-p)^(n-k)`를 적용하고, 같은 식을 독립 계산해 `0.3125`를 검산한다.
