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
  - ../../../scripts/collect_ebsi_math_archive.py
  - ../../../scripts/diagnose_pdf_engine_ingestion.py
  - ../../../engine/rule_based_nlp.py
  - ../../../engine/mini_neural_router.py
  - ../../../engine/tool_routing.py
  - ../../../scripts/train_local_tool_embedder.py
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

## 공개 수학 모델 평가셋

GSM8K의 MIT 라이선스 `main/test` 1,319문항은 실제 생성형 수학 모델의 별도 평가셋으로만 로컬에 보관한다. 학습 분할은 이 명령으로 내려받지 않으며, 문제·풀이 전문과 정답은 `private_benchmarks/public/gsm8k_main_test`에만 쓴다.

```powershell
python scripts/import_hf_gsm8k_benchmark.py --output-dir private_benchmarks\public\gsm8k_main_test
```

생성형 모델 평가는 현재 규칙·라우터 실험과 섞지 않는다. 모델명·커밋·프롬프트·추론 설정·정규화된 최종 답·정답 정확도·실패 유형을 별도 private 보고서로 기록한다. 한국어 평가용 Ko-GSM8K는 배포 페이지에서 약관·연락처 공유 동의가 필요하므로, 사용자가 해당 접근을 수락하기 전에는 자동 수집하지 않는다.

LM Studio 또는 llama.cpp server처럼 OpenAI Chat Completions 호환의 **로컬** 서버를 실행한 뒤에는 아래 명령으로 평가한다. 모델 가중치와 문항 원문·응답은 모두 private 경로에 남고, 이 보고서는 도구 라우팅 지표에 합산하지 않는다.

```powershell
python scripts/evaluate_local_math_model.py --model <로컬-서버의-모델-ID> --limit 20
```

기본 서버 주소는 `http://127.0.0.1:1234/v1`이며, 다른 주소는 `--api-base`로 명시한다. 스크립트는 각 문항 뒤 중간 보고서를 저장하므로 실행이 끊겨도 마지막 완료 문항까지의 결과를 보존한다.

GSM8K로 현재 도구 라우터 자체를 점검할 때는 초등 서술형 산수 전용 계약이 없다는 사실을 유지한다. 즉 정답 정확도를 주장하는 코퍼스가 아니라, 1,319문항에서 도구가 임의 `PASS`를 내지 않는지 확인하는 미지원 거부 평가다.

```powershell
python scripts/adapt_gsm8k_for_router_experiment.py
python scripts/run_router_experiment.py --corpus private_benchmarks\public\gsm8k_main_test\gsm8k_router_rejection_corpus.json --output private_benchmarks\reports\gsm8k_router_rejection_report.json
```

### 내부 신경망 거부 튜닝

`mini-neural-router-v2-reject-profile`은 기존 도구 계약의 양성 문장만 학습하던 MLP에, 저장소에서 합성한 일반 서술형 산수 hard-negative를 `__reject__` 클래스로 추가한다. GSM8K·공식 기출 전문은 이 MLP의 학습 입력으로 사용하지 않는다. 거부 클래스가 우세하면서 긴 영어 서술형 또는 명시적 한국어 생활 산수 신호가 있을 때만 후보 생성을 중단한다. 수식·고교 개념 표지가 있으면 reject 확률만으로 차단하지 않아 기존 LaTeX 회귀를 보존한다.

확률 도구는 `%` 단독으로 실행하지 않는다. 할인율·증가율 같은 일반 산수를 확률로 오인하지 않기 위해 `확률`, `조합`, `순열`, `경우의 수`, `주사위`, `동전` 가운데 하나가 필요하다. 이 정책은 라우터에 공통 적용된다.

2026-07-29 로컬 결과는 다음과 같다.

| 코퍼스 | 라우터 | 허위 PASS | 미지원 거부 | 결정성 | 평균 처리 시간 |
| --- | --- | ---: | ---: | ---: | ---: |
| GSM8K main/test 1,319문항 | neural v2 | 0.0% | 100.0% | 100.0% | 1.72 ms |
| 2027학년도 6월 공식 코퍼스 10문항 | neural v2 | 0.0% | 100.0% | 100.0% | 공식 지원 문항 정답·검산 100.0% |

같은 문항에서 미니 MLP를 후보마다 다시 계산하지 않고 문항당 한 번만 순전파하도록 최적화했다. 이 변경은 후보 순서를 바꾸지 않으며, GSM8K 전수의 평균 처리 시간을 약 90ms 수준에서 1.72ms로 낮췄다.

### 로컬 임베더 홀드아웃 재학습 (2026-07-29)

`train_local_tool_embedder.py`는 라벨별 고정 80:20 홀드아웃을 먼저 분리하고, 훈련 분할만으로 도구 중심 벡터를 만든다. 따라서 저장되는 `holdout_evaluation.json`의 정확도와 macro-F1은 학습에 포함되지 않은 OMJ 문항의 도구 감지 지표다. 기존 전체 데이터 중심 벡터에 대한 재평가와 혼동하지 않는다.

저메모리 CPU 실행(`batch-size=1`, `max-length=96`, 3 epoch) 결과는 다음과 같다.

| 학습 데이터 | 학습/홀드아웃 | 라벨 수 | 홀드아웃 정확도 | Macro-F1 |
| --- | ---: | ---: | ---: | ---: |
| OMJ 규칙 검산 통과 문항 | 309 / 77 | 10 | 89.61% | 87.93% |

모델 산출물은 `private_models/tool-embedder-v2-lowmem`에만 보관한다. 같은 모델의 2027학년도 6월 공식 로컬 코퍼스 10문항 평가에서 embedding 라우터는 지원 문항 정답·검산 100%, 미지원 거부 100%, 허위 PASS 0%, 평균 357.87ms를 기록했다. 이 공식 코퍼스는 10문항의 작은 회귀셋이므로 전국 단위 일반 정확도로 해석하지 않는다. 10개년 수능·모의평가 전체 원문이 로컬 private 코퍼스로 구축된 뒤, 같은 분할 밖의 고정 시험셋으로 다시 측정해야 한다.

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

### EBSi 10개년 수학 원문 인덱스 (2026-07-29)

`collect_ebsi_math_archive.py`는 EBSi 공개 기출 목록의 AJAX 응답에서 수학 문제 PDF와 정답 자산 URL만 찾아낸다. 달력 연도 2016~2025의 6·9·11월을 기본 대상에 두며, 원문은 `private_benchmarks/official/ebsi_10y_math_assets` 밖으로 복사하지 않는다. `manifest.json`에는 URL·SHA-256·자산 종류를, `sessions.json`에는 시행일·선택과목별 문제/정답 연결을 남긴다.

```powershell
python scripts/collect_ebsi_math_archive.py --start-year 2016 --end-year 2025 --months 06,09,11 --download
```

2026-07-29 실제 수집 결과는 문제 PDF 48개, 정답 이미지 24개, 총 72개 자산(약 42.8MB)과 20개 시행일·과목 묶음이다. 선택과목 체제 이전 회차는 공통 수학으로, 이후 `확률과 통계`·`미적분`·`기하`로 인덱싱된다. 정답 이미지가 홀·짝 문제지마다 별도 제공되지 않는 회차가 있으므로, 문제 PDF 수와 정답 자산 수가 같아야 한다는 검증 조건은 사용하지 않는다. 이 인덱스는 원문 보관·OCR·문항 분할의 입력일 뿐 학습 정답 데이터가 아니다. OCR 및 정답 대조를 거쳐 문항별 구조화가 끝난 레코드만 별도 학습/평가 분할에 넣는다.

`diagnose_pdf_engine_ingestion.py`로 2025년 11월 수능 수학(확률과 통계 선택) PDF의 30문항을 PyMuPDF 원문 텍스트 그대로 현재 엔진에 전달했다. 실행 `PASS`는 4/30(13.3%)였으나 공식 정답표를 원본 이미지로 대조한 결과 네 건 모두 오답이었다. 따라서 **원문 PDF→현재 엔진 종단간 정확도는 0/30, 허위 PASS는 4건**이다. 이 수치는 정답 정확도 검증을 끝낸 표본 결과이며, 10개년 정확도로 일반화하지 않는다. 사설 수식 글리프 정규화와 도구별 입력 계약이 완료되기 전에는 PDF 원문을 곧바로 API 입력으로 제공하지 않는다.

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
