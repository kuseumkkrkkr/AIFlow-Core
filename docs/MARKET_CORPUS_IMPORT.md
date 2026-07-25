# 문제집 코퍼스 투입·검증 가이드

## 권장 레코드

사용자가 합법적으로 보유한 문제를 UTF-8 JSONL로 저장한다. 원문 파일 자체는 저장소에 올리지 않고 로컬에서만 사용한다.

```json
{"case_id":"book-001","source_label":"내 문제집 3-1","curriculum":"중3","question":"4x+3=27에서 x의 값","expected":6}
```

필수 필드:

- `question`: 문제 문장
- `expected`: 공식 정답(숫자 또는 문자열)

선택 필드:

- `case_id`
- `source_label`
- `curriculum`

## 로컬 검증

```powershell
python engine/corpus_runner.py C:/private/my_questions.jsonl `
  --repeats 10 `
  --output docs/private_corpus_report.json
```

보고서에는 실제 답, 기대 답, 분류 도메인, 선택 규칙, 공식, 풀이 단계, 독립 검산, 실패 사유가 기록된다. `--repeats`를 사용하면 동일 코퍼스를 여러 번 실행해 결과 결정성도 `deterministic` 필드로 확인한다.

## 온라인 검증

문제 원문을 저장하지 않고 HTTPS 요청 본문으로만 보낼 수 있다.

```json
POST https://aiflow-core-v05.vercel.app/api/corpus
{"cases":[{"case_id":"q1","curriculum":"수1","question":"지수방정식 2^x=16","expected":4}]}
```

한 요청은 최대 100문항이며, 실패 문항도 전체 결과와 함께 반환된다. 실제 문제집을 검증할 때는 출처와 이용 권한을 `source_label`에 남기고, 원문 PDF·이미지는 Git에 커밋하지 않는다.

## 해석 실패 처리

지원하지 않는 표현은 임의 정답으로 대체하지 않고 `FAIL`로 남긴다. 실패 보고서를 유형별로 모아 새 규칙·별칭·슬롯 추출기·검산 테스트를 추가한 뒤 동일 코퍼스를 다시 실행한다.
