---
type: home
project: AIFlow-Core
version: v0.5
last_verified: 2026-07-28
sources:
  - ../../../engine/rule_based_nlp.py
  - ../../../engine/problem_generation_loop.py
  - ../../../api/solve.py
---

# AIFlow-Core 연구 Vault

AIFlow-Core는 자연어 수학 문제를 **명시적 규칙과 지식 베이스**로 해석하고, 풀이 단계와 독립 검산을 함께 반환하는 결정론적 수학 엔진이다.

## 빠른 이동

- [[10 Architecture/System Map|시스템 구성도]] — 웹·API·엔진·지식·검증 레이어
- [[10 Architecture/Code Map|코드 구성표]] — 파일별 책임과 진입점
- [[20 Flows/Solve Request Flow|문제 풀이 플로우]] — 한 문항이 PASS/FAIL에 도달하는 과정
- [[20 Flows/Geometry GUI Flow|기하 GUI 입력 플로우]] — 구조화된 좌표 도형의 풀이·검산
- [[20 Flows/Generation and Corpus Flow|생성·코퍼스 검증 플로우]] — 난이도 계약과 실제 문항 검증
- [[30 Reference/Knowledge Base and Contracts|지식 베이스·계약]] — JSON 지식 구조와 난이도 정책
- [[30 Reference/Verification and Operations|검증·운영]] — 로컬 검증과 Vercel API

## 핵심 원칙

1. 해석이 불충분하면 임의 답을 만들지 않고 `FAIL`을 반환한다.
2. `PASS`는 규칙 계산, 기대값 일치(코퍼스·생성 시), 독립 검산이 모두 성립할 때만 인정한다.
3. 지식 카탈로그에 있다는 사실과 실행 규칙으로 지원된다는 사실을 구분한다.
4. 모든 지식·보고서 파일은 UTF-8로 읽고 쓴다.

## 현재 경계

이 엔진은 범용 LLM이 아니다. 현재 지원하는 문장·수식 패턴을 규칙으로 안정적으로 계산하는 실행 계층이며, 자연어 해석의 범위를 넓힐 때마다 반드시 회귀 문항과 검산 규칙을 추가한다.
