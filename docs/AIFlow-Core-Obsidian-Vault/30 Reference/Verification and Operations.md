---
type: runbook
last_verified: 2026-07-28
sources:
  - ../../../scripts/continuous_validation.ps1
  - ../../../vercel.json
  - ../../../tests
---

# 검증·운영

## 로컬 검증

저장소 루트에서 실행한다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/continuous_validation.ps1
python tests/test_api_serialization.py
python engine/corpus_runner.py benchmarks/official_exam_regression.json --repeats 20
```

검증 스크립트는 핵심 규칙, 생성 루프, 난이도 입력 검증, seed 매트릭스, 코퍼스 회귀를 실행한다. 보고서는 UTF-8 JSON으로 `docs/`에 기록한다.

## API 운영 한계

| API | 제한 | 목적 |
| --- | ---: | --- |
| `/api/solve` | 요청 200 KB | 단일 문제 풀이 |
| `/api/generate` | 반복 1~20, 요청 30 KB | 생성·검산 루프 |
| `/api/corpus` | 1~100문항, 요청 100 KB | 일괄 회귀 검증 |
| `/api/algorithm` | 읽기 전용 | 알고리즘·지식 공개 |

## 배포 확인

Vercel 배포 후 다음 두 가지를 확인한다.

1. `/api/algorithm`에서 `curriculum_knowledge.subjects`에 다섯 과목이 반환되는가.
2. 새 규칙의 `/api/solve` 입력이 `PASS`, 기대 정답, `verified=true`을 모두 반환하는가.

## 변경 후 Vault 갱신

아키텍처·API·지식 구조·검증 계약이 바뀌면 관련 노트의 `last_verified`와 `sources`를 같은 커밋에서 갱신한다.
