"""GSM8K test를 AIFlow 라우터의 비공개 미지원-거부 평가 코퍼스로 변환한다.

GSM8K는 초등 서술형 산수 평가셋이며, 현 AIFlow-Core의 고교 수식 도구 계약에는
정답 도구가 정의되어 있지 않다. 그러므로 이 변환기는 문항을 억지로 지원으로
표기하지 않고 모두 미지원으로 기록하여 허위 PASS와 안전한 거부를 측정한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def adapt_records(source: Path) -> list[dict]:
    """변수: GSM8K UTF-8 원본 배열. 원리: 원문과 정답을 보존하되 AIFlow 실험 필수 메타데이터를 채운다."""
    records = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError("GSM8K 원본은 비어 있지 않은 배열이어야 합니다.")
    document_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    adapted: list[dict] = []
    for index, record in enumerate(records, start=1):
        question = str(record.get("question", "")).strip()
        expected = str(record.get("expected", "")).strip()
        if not question or not expected:
            raise ValueError(f"GSM8K {index}번 문항에 문제 또는 정답이 없습니다.")
        adapted.append({
            "case_id": f"gsm8k-router-{index:04d}",
            "source": "openai/gsm8k main test (MIT)",
            "source_document_sha256": document_hash,
            "question_number": index,
            "question": question,
            "latex_question": question,
            "expected": expected,
            "curriculum": "GSM8K 초등 서술형 산수",
            "diagram_dependent": False,
            "supported": False,
            "question_hash": hashlib.sha256(question.encode("utf-8")).hexdigest(),
            "unsupported_reason": "현재 AIFlow-Core에는 GSM8K 자연어 산수 전용 도구 계약이 없다.",
        })
    return adapted


def main() -> None:
    """변수: 입력·출력 경로. 원리: 저작권·평가 원문을 private 경로 안에서만 변환한다."""
    parser = argparse.ArgumentParser(description="GSM8K를 AIFlow 미지원-거부 평가 코퍼스로 변환합니다.")
    parser.add_argument("--input", default="private_benchmarks/public/gsm8k_main_test/gsm8k_main_test.json")
    parser.add_argument("--output", default="private_benchmarks/public/gsm8k_main_test/gsm8k_router_rejection_corpus.json")
    args = parser.parse_args()
    output = Path(args.output)
    if "private_benchmarks" not in {part.lower() for part in output.parts}:
        raise SystemExit("GSM8K 전문은 private_benchmarks 아래에만 저장해야 합니다.")
    output.parent.mkdir(parents=True, exist_ok=True)
    records = adapt_records(Path(args.input))
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "records": len(records), "supported": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
