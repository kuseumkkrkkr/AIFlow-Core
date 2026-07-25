# AIFlow-Core v0.5 설계 문서

## 무엇을 가지고 있는가

`knowledge/`는 UTF-8 JSON 지식 베이스다. `concept_graph.json`은 개념·별칭·선행관계, `rule_library.json`은 적용 조건·필요 변수·공식·검산 정책, `template_pack.json`은 문제 생성 템플릿, `validation_contract.json`은 PASS/FAIL 계약을 담는다. 현재 일차·이차방정식, 비율, 집합, 확률·조합·순열, 기본 도형, 등차수열, 함수값·합성함수·역함수, 인수분해·나머지정리, 조건부확률, 지수·로그와 지수·로그 방정식, 특수각 삼각함수, 다항식 극한, 거듭제곱 미분·접선 기울기, 단항식 정적분을 다룬다.

## 처리 파이프라인

1. 입력을 NFKC와 유니코드 숫자로 정규화한다.
2. 별칭과 수식 패턴을 점수화해 도메인을 분류한다.
3. 계수·첫항·공차·집합 크기 같은 슬롯을 구조화한다.
4. 누락 슬롯, 위험도, 필요한 변수 수로 최적 규칙 경로를 고른다.
5. 공식→대입→계산→약분→재대입 순서의 풀이 trace를 만든다.
6. 별도 검산 함수로 결과를 재확인하며, 해석이 부족하면 임의 답 대신 FAIL을 반환한다.

## 수학 LLM의 초석인 이유

이 코어는 LLM 자체가 아니라 명시적 지식 실행 계층이다. (1) 풀이가 포함된 합성 학습 데이터 생성기, (2) 모델 출력의 독립 채점기, (3) 회귀 평가 기준선, (4) 개념 그래프 기반 검색 계층으로 사용할 수 있다. LLM은 자연어 해석과 가설 생성에 쓰고, 공식 적용·최종 판정은 결정론적 코어가 담당하는 하이브리드 구성이 안전하다.

## 검증과 한계

독립 변형 문항 12개와 고난도 변형 문항 11개가 현재 100% 통과한다. 생성 루프에는 새 수1·수2 영역을 포함해 20개 템플릿을 3회 반복한 60개 케이스가 들어가며 현재 60/60 통과한다. 이는 명시적으로 지원하는 구조에 대한 결과이지 모든 시중 문제집의 정확도를 의미하지 않는다. 다음 단계는 함수의 정의역·치역, 다항식 나머지의 일반형, 도형 조건 해석, 자연어 애매성 평가를 확장하는 것이다.

## 반복 문제 생성 루프

`engine/problem_generation_loop.py`의 `GenerationConfig`는 `min_grade`, `max_grade`, `repeats`, `seed`, `include_mock`를 입력으로 받는다. 생성기는 원문 문제집을 복제하지 않고 중3·고1·수1·수2·고2 모의고사 스타일의 구조화된 변형 문항을 만든다. 각 문항은 독립 기대 정답, 분류 도메인, 선택 규칙, 풀이 단계 수, 검산 결과를 함께 저장한다.

```powershell
python engine/problem_generation_loop.py
# SUMMARY passed=60 total=60 rate=1.000
python engine/problem_generation_loop.py --min-grade 수1 --max-grade 수2 --repeats 10 --seed 99 --output docs/s1s2_report.json
python engine/problem_generation_loop.py --difficulty hard --repeats 5 --seed 2026 --output docs/hard_report.json
```

결과는 `docs/generated_validation_report.json`에 UTF-8로 기록된다. 이 보고서는 “생성 성공”만 세지 않고 `status=PASS`, 기대 정답 일치, `verified=true`, 풀이 trace 존재를 모두 만족해야 통과시킨다. 실제 시중 모의고사 원문 전체를 자동 수집·복제한 결과는 아니며, 저작권을 피한 독립 변형 기반의 회귀 기준선이다.

## 다중 seed 벤치마크

대규모 실행 기록: seed 1~20을 5회 반복해 총 3,700문항을 생성했고 3,700/3,700 PASS(100%)였다. 고2 프로필은 수1·수2·고2 누적 범위로 집계한다. 상세 결과는 `docs/benchmark_matrix_3100_report.json`에 저장했다. 이 수치는 현재 생성 템플릿과 명시적 규칙 범위의 회귀 안정성을 의미하며 실제 시중 문제집 전체의 일반화 정확도와 동일한 의미는 아니다.

`engine/run_benchmark_matrix.py`는 중3·고1·수1·수2·고2 프로필을 여러 seed로 반복한다. 현재 `11,22,33,44,55` seed와 2회 반복으로 총 200문항을 실행했고 200/200 PASS였다. `docs/benchmark_matrix_report.json`에는 도메인별 통과율도 저장된다.

```powershell
python engine/run_benchmark_matrix.py --seeds 11,22,33,44,55 --repeats 2
```

웹 생성 API도 같은 계약을 사용한다.

```json
POST /api/generate
{"min_grade":"수1","max_grade":"수2","repeats":2,"seed":101,"include_mock":false}
```

응답에는 `summary`(총 문항·통과율)와 각 문항의 문제, 기대 정답, 실제 정답, 공식, 풀이 trace, 독립 검산 결과가 포함된다. `repeats`는 운영 보호를 위해 1~20으로 제한한다.
난이도 파라미터는 `basic`, `mixed`, `hard`를 지원하며 basic은 중3·고1 템플릿, hard는 수1·수2·고2 모의고사형 템플릿을 선택한다.

## 문제집 코퍼스 검증

온라인 API로도 최대 100문항을 한 번에 검증할 수 있다.

```json
POST /api/corpus
{"cases":[{"case_id":"q1","curriculum":"수1","question":"지수방정식 2^x=16","expected":4}]}
```

사용자가 보유한 합법적인 JSONL/JSON 문제 파일은 다음처럼 검증할 수 있다.

```powershell
python engine/corpus_runner.py path/to/questions.jsonl --output docs/corpus_validation_report.json
```

각 레코드는 최소 `question`, `expected`를 가지며 `case_id`, `source_label`, `curriculum`을 선택적으로 기록한다. 저장소의 `benchmarks/market_style_corpus.json`은 원문 문제집을 복제하지 않은 독립 모의고사형 23문항 예제이며 현재 23/23 통과한다. 지수·로그 방정식과 접선 기울기 문항도 포함한다.

