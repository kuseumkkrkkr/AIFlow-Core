---
type: runbook
last_verified: 2026-07-29
sources:
  - ../../../scripts/continuous_validation.ps1
  - ../../../vercel.json
  - ../../../tests
  - ../../../scripts/build_local_tool_dataset.py
  - ../../../scripts/train_local_tool_embedder.py
  - ../../../scripts/import_official_pdf_corpus.py
  - ../../../scripts/render_private_pdf_pages.py
  - ../../../scripts/extract_official_exam_ocr.ps1
  - ../../../engine/rule_based_nlp.py
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

## 로컬 임베더 학습

도구 감지 임베더는 답을 생성하는 모델이 아니라, 문제와 풀이의 구조에 맞는 기존 수학 도구 후보를 검색하는 로컬 모델이다. OMJ 데이터 추출은 아래 테이블만 read-only로 사용한다.

- `quest_data`: 문제 본문·정답·태그
- `solve_step`: 생성·저장된 풀이 단계

학습 레이블은 문제 원문을 기존 규칙 엔진으로 풀었을 때 `PASS`와 독립 검산을 함께 만족한 도구로만 만든다. 사용자 답안, 사용자 식별자, 채팅, 제출 이력은 사용하지 않는다.

```powershell
$env:HF_HOME = 'D:\AIFlow-Core\private_models\huggingface'
python scripts/build_local_tool_dataset.py --database private_data\omj\quests.db --output-dir private_benchmarks\local_embedder
python scripts/train_local_tool_embedder.py --dataset private_benchmarks\local_embedder\omj_tool_detection.jsonl --output-dir private_models\tool-embedder-v1 --epochs 2
$env:AIFLOW_LOCAL_EMBEDDER_DIR = 'D:\AIFlow-Core\private_models\tool-embedder-v1'
python scripts/run_router_experiment.py --corpus private_benchmarks\official\2026_06_g2_math.json --output private_benchmarks\reports\2026_06_g2_router_report.json
```

기본 모델은 `intfloat/multilingual-e5-small`이며, 로컬 디스크에 모델·체크포인트를 위한 충분한 여유 공간이 있어야 한다. `tool_prototypes.json`까지 생성되면 `embedding` 라우터는 실제 E5 문항 벡터와 도구별 중심 벡터를 코사인 검색한다. 체크포인트가 없는 Vercel 기본 경로는 의존성 없는 char n-gram 기준선으로만 동작하며, `/api/algorithm`의 `routing_experiments.embedding.available_in_this_runtime`과 `local_model_version`으로 둘을 구분한다. 이 데이터와 모델은 `private_*` 경로로 Git·Vercel에서 제외된다.

검증 스크립트는 핵심 규칙, 생성 루프, 난이도 입력 검증, seed 매트릭스, 코퍼스 회귀를 실행한다. 보고서는 UTF-8 JSON으로 `docs/`에 기록한다.

`private_benchmarks/`는 Git에서 제외된다. 공개 기출·문제집 전문·PDF·이미지는 이 경로에만 보관하고, 저장소에는 출처·문항번호·원문 SHA-256·집계 결과만 남긴다. `engine/experiment_runner.py`는 실행 전에 문항 전문·LaTeX·정답·출처 문서 해시·문항 번호·교육과정·그림 의존·지원 여부를 검증하고, 같은 전문으로 `rule`, `neural`, `embedding`을 비교해 도구 선택 정확도, 정답 정확도, 검산 통과율, 허위 PASS율, 미지원 거부 정확도, 평균 처리 시간, 반복 실행 결정성 및 단원별 지표를 각각 기록한다. embedding 보고서에는 실제 로컬 E5·도메인 투영 모델 사용 여부와 버전도 기록한다.

## 공식 PDF 수집

평가원 등 원문 공개처의 문제지와 정답표는 아래처럼 **로컬 전용**으로 수집한다. 수집기는 원문을 Git·Vercel에 쓰지 않고, 재현을 위해 URL과 SHA-256만 `manifest.json`에 남긴다.

```powershell
python scripts/import_official_pdf_corpus.py --exam-id kice_2027_06 --question-url https://cdn2.kice.re.kr/suneung27mo06/suneung27mo06_2.pdf --answer-url https://cdn2.kice.re.kr/suneung27mo06/suneung27mo06_2a.pdf --output-dir private_benchmarks\official\kice_2027_06
```

PDF 수식 폰트가 텍스트 추출에서 사설영역 문자로 깨질 때는 Windows 내장 한국어 OCR을 쓴다. PDF 원문과 렌더 PNG·OCR 결과는 모두 비공개 경로에만 둔다. OCR 수식은 오류가 날 수 있으므로 원본 이미지·정답표와의 대조 전에는 코퍼스 정답 데이터로 승격하지 않는다.

```powershell
python scripts/render_private_pdf_pages.py --pdf private_benchmarks\official\kice_2027_06\suneung27mo06_2.pdf --output-dir private_benchmarks\official\kice_2027_06\ocr_pages --scale 2
Get-ChildItem private_benchmarks\official\kice_2027_06\ocr_pages\page-*.png | ForEach-Object {
  powershell -ExecutionPolicy Bypass -File scripts\extract_official_exam_ocr.ps1 -ImagePath $_.FullName -OutputDirectory private_benchmarks\official\kice_2027_06\ocr_text
}
```

2027학년도 6월 수학 영역의 로컬 점검에서는 원문 해시를 붙인 문항을 `private_benchmarks/official/kice_2027_06/corpus.json`에만 추가한다. 이 코퍼스에서 확인된 `a^(mx+p)=b^(nx+q)`, 이차다항식 차분몫, 원점 동시 출발에서 `v₁(t)=at²+bt`, `v₂(t)=ct`인 두 점의 위치 일치 시각, `p=q^r`인 두 로그 밑의 연립 비는 실행 계약으로 승격한다. 속도 계약은 `t=3(c-b)/(2a)>0` 및 위치 차 재대입을, 로그 계약은 공통 밑 좌표 `x=log_q(a), y=log_q(b)`의 두 선형식을 모두 재대입하는 것을 요구한다. 그림 의존 극한, 일반 삼각·로그 식은 성공값을 추정하지 않고 `FAIL`로 남긴다. 보고서의 허위 `PASS`율은 이 미지원 문항까지 포함해 계산한다.

라우터 회귀에는 지원 문항뿐 아니라 해가 유일하지 않거나 필수 표현이 빠진 문항도 둔다. 이 경우 유사한 숫자 패턴을 가진 다른 도구가 `PASS`하지 않아야 하며, 예를 들어 정적분 도구는 `정적분`·`부정적분`·`적분` 중 하나가 없는 입력을 실행하지 않는다.

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
