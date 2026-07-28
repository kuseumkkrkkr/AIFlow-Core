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
python tests/test_latex_and_routing.py
python -c "import sys; sys.path.insert(0, 'engine'); from experiment_runner import run_experiment; print(run_experiment('private_benchmarks/official/corpus.json'))"
```

검증 스크립트는 핵심 규칙, 생성 루프, 난이도 입력 검증, seed 매트릭스, 코퍼스 회귀를 실행한다. 보고서는 UTF-8 JSON으로 `docs/`에 기록한다.

`private_benchmarks/`는 Git에서 제외된다. 공개 기출·문제집 전문·PDF·이미지는 이 경로에만 보관하고, 저장소에는 출처·문항번호·원문 SHA-256·집계 결과만 남긴다. `engine/experiment_runner.py`는 실행 전에 문항 전문·LaTeX·정답·출처 문서 해시·문항 번호·교육과정·그림 의존·지원 여부를 검증하고, 같은 전문으로 `rule`, `neural`, `embedding`을 비교해 도구 선택 정확도, 정답 정확도, 검산 통과율, 허위 PASS율, 미지원 거부 정확도, 평균 처리 시간을 각각 기록한다.

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
