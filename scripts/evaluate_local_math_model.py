"""로컬 생성형 수학 모델을 비공개 GSM8K 평가셋으로 측정한다.

이 스크립트는 LM Studio, llama.cpp server 등 OpenAI Chat Completions 호환의
로컬 서버에만 요청한다. 문제와 생성 답안은 ``private_benchmarks`` 밖으로 쓰지
않으며, 규칙 기반 도구·라우터 성능과 생성 모델 성능을 섞지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SYSTEM_PROMPT = (
    "You solve grade-school math problems. Work privately, then end with one line exactly "
    "in the form FINAL: <answer>. Do not add a unit or explanation on that final line."
)
FINAL_PATTERN = re.compile(r"(?:FINAL|####)\s*:\?\s*([^\n]+)", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?(?:/[-+]?\d[\d,]*(?:\.\d+)?)?")


def normalize_answer(value: object) -> str | None:
    """변수: 모델 또는 정답 문자열. 원리: 쉼표·통화기호·표기 차이만 제거해 수치 정답을 비교한다."""
    text = str(value).strip().replace("$", "").replace(",", "")
    text = text.rstrip(".").strip()
    if not text:
        return None
    if "/" in text and re.fullmatch(r"[-+]?\d+(?:\.\d+)?/[-+]?\d+(?:\.\d+)?", text):
        numerator, denominator = text.split("/", 1)
        try:
            if Decimal(denominator) == 0:
                return None
            return _decimal_text(Decimal(numerator) / Decimal(denominator))
        except InvalidOperation:
            return None
    try:
        return _decimal_text(Decimal(text))
    except InvalidOperation:
        return None


def _decimal_text(value: Decimal) -> str:
    """변수: Decimal 수치. 원리: 정수의 유효한 끝자리 0은 보존하고 소수부의 불필요한 0만 제거한다."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def extract_final_answer(response: str) -> str | None:
    """변수: 모델 원문 응답. 원리: FINAL 표기를 우선하고 없으면 마지막 수치 토큰만 보수적으로 사용한다."""
    matches = FINAL_PATTERN.findall(response)
    candidate = matches[-1].strip() if matches else ""
    if candidate:
        numbers = NUMBER_PATTERN.findall(candidate)
        normalized = normalize_answer(numbers[-1]) if numbers else normalize_answer(candidate)
        if normalized is not None:
            return normalized
    numbers = NUMBER_PATTERN.findall(response)
    return normalize_answer(numbers[-1]) if numbers else None


def request_completion(
    api_base: str, model: str, question: str, timeout: float, temperature: float, api_key: str | None,
) -> tuple[str, float]:
    """변수: 로컬 서버 주소·모델·문항·추론 설정. 원리: 고정 Chat Completions 요청과 경과 시간을 반환한다."""
    endpoint = f"{api_base.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310: 사용자가 지정한 로컬 OpenAI 호환 주소다.
            body = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(f"로컬 모델 요청 실패: {error}") from error
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("로컬 서버 응답에 choices[0].message.content가 없습니다.") from error
    return str(content), elapsed_ms


def evaluate(
    corpus_path: Path, output_path: Path, api_base: str, model: str, timeout: float,
    temperature: float, limit: int | None, api_key: str | None,
) -> dict[str, Any]:
    """변수: 코퍼스·출력·모델 설정. 원리: 각 문항의 원문 응답·정규 답·시간을 private JSON 보고서로 누적한다."""
    records = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("코퍼스 최상위 값은 문항 배열이어야 합니다.")
    selected = records[:limit] if limit is not None else records
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for index, record in enumerate(selected, start=1):
        question = str(record.get("question", ""))
        expected = normalize_answer(record.get("expected"))
        response, elapsed_ms = request_completion(api_base, model, question, timeout, temperature, api_key)
        predicted = extract_final_answer(response)
        results.append({
            "case_id": record.get("case_id"), "expected": expected, "predicted": predicted,
            "correct": predicted == expected and expected is not None,
            "elapsed_ms": elapsed_ms, "raw_response": response,
        })
        report = _build_report(corpus_path, api_base, model, timeout, temperature, results, len(selected), complete=False)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{index}/{len(selected)}] {record.get('case_id')} {'PASS' if results[-1]['correct'] else 'FAIL'}")
    report = _build_report(corpus_path, api_base, model, timeout, temperature, results, len(selected), complete=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _build_report(
    corpus_path: Path, api_base: str, model: str, timeout: float, temperature: float,
    results: list[dict[str, Any]], total: int, complete: bool,
) -> dict[str, Any]:
    """변수: 설정·문항별 결과. 원리: 중간 저장도 가능한 정확도·실패 유형·시간 집계 보고서를 구성한다."""
    completed = len(results)
    correct = sum(bool(result["correct"]) for result in results)
    parse_failures = sum(result["predicted"] is None for result in results)
    elapsed = [float(result["elapsed_ms"]) for result in results]
    return {
        "kind": "generative_math_model_evaluation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "complete": complete,
        "corpus": str(corpus_path),
        "model": {"name": model, "api_base": api_base, "backend": "openai_compatible_local"},
        "prompt": SYSTEM_PROMPT,
        "inference": {"temperature": temperature, "timeout_seconds": timeout},
        "metrics": {
            "requested_cases": total, "completed_cases": completed, "correct_cases": correct,
            "exact_answer_accuracy": correct / completed if completed else 0.0,
            "final_answer_parse_failure_rate": parse_failures / completed if completed else 0.0,
            "mean_elapsed_ms": sum(elapsed) / completed if completed else 0.0,
        },
        "results": results,
    }


def main() -> None:
    """변수: CLI 옵션. 원리: 로컬 서버와 private GSM8K 파일을 명시적으로 받아 재현 가능한 평가를 시작한다."""
    parser = argparse.ArgumentParser(description="로컬 OpenAI 호환 수학 모델을 GSM8K로 평가합니다.")
    parser.add_argument("--corpus", default="private_benchmarks/public/gsm8k_main_test/gsm8k_main_test.json")
    parser.add_argument("--output", default="private_benchmarks/reports/gsm8k_local_model_report.json")
    parser.add_argument("--api-base", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", required=True, help="로컬 서버에 등록된 모델 식별자")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.timeout <= 0 or not 0 <= args.temperature <= 2 or args.limit is not None and args.limit < 1:
        raise SystemExit("timeout은 양수, temperature는 0~2, limit은 양수여야 합니다.")
    report = evaluate(Path(args.corpus), Path(args.output), args.api_base, args.model, args.timeout, args.temperature,
                      args.limit, os.environ.get("AIFLOW_LOCAL_MODEL_API_KEY"))
    print(json.dumps(report["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
