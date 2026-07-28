---
type: flow
last_verified: 2026-07-28
sources:
  - ../../../api/solve.py
  - ../../../engine/rule_based_nlp.py
---

# 문제 풀이 플로우

```mermaid
flowchart TD
    A[문제 문자열] --> B{크기 1~200,000 bytes?}
    B -- 아니오 --> R400[HTTP 413 FAIL]
    B -- 예 --> C[UTF-8 JSON decode]
    C --> D[normalize_text<br/>NFKC · 유니코드 숫자 통일]
    D --> E[classify<br/>키워드·수식 패턴 점수화]
    E --> F[_extract_slots<br/>계수·항·확률·벡터 성분 추출]
    F --> G[select_optimal_rule<br/>누락 슬롯·위험도·단계 수 비교]
    G --> H[solve_rule]
    H --> I{규칙의 입력 조건 충족?}
    I -- 아니오 --> J[FAIL + reason]
    I -- 예 --> K[verify_result<br/>독립 불변식 재계산]
    K --> L{검산 통과?}
    L -- 아니오 --> J
    L -- 예 --> M[build_solution_trace]
    M --> N[UTF-8 JSON PASS 응답]
```

## 응답 계약

`/api/solve` 응답은 `status`, `parse`, `path`, `result`, `steps`, `summary`를 갖는다.

- `parse`: 정규화 문장, 도메인, 태그, 슬롯, 누락 슬롯, 신뢰도
- `path`: 실제 선택된 규칙 ID
- `result`: 정답, 공식, 검산 결과 또는 실패 이유
- `steps`: 학생에게 보여 줄 순서형 풀이

`Fraction`처럼 기본 JSON이 표현하지 못하는 수학 객체는 정확한 문자열(예: `"1/2"`)로 보존한다.

## 예시: 이항분포

`이항분포 n=5, p=1/2에서 X=2일 확률`은 `stat_binomial_distribution`으로 분류된다. 슬롯 `n=5, p=1/2, k=2`를 추출한 뒤 `nCk·p^k·(1-p)^(n-k)`를 적용하고, 같은 식을 독립 계산해 `0.3125`를 검산한다.
