"""비공개 수학 PDF가 현재 규칙 엔진에 직접 입력 가능한지 진단한다.

필요 변수: private_benchmarks 하위 PDF, 결과 JSON 경로.
작동 원리: PyMuPDF 텍스트에서 문항 번호 경계를 찾고 각 블록을 현재 분류기·규칙
엔진에 그대로 전달한다. 이 결과는 정답표 대조가 없으므로 정답 정확도가 아니라
원문 글꼴·OCR을 포함한 직접 입력 가능률과 실패 사유를 기록하는 진단이다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = (ROOT / "private_benchmarks").resolve()
# 스크립트 직접 실행 시에도 엔진 내부의 상대 없는 import가 해석되도록 engine 경로를 넣는다.
sys.path.insert(0, str(ROOT / "engine"))
from rule_based_nlp import classify, solve_rule  # noqa: E402

QUESTION_BOUNDARY = re.compile(r"(?m)^\s*(?P<number>[1-9]|[12]\d|30)\.\s*")


def _private_file(value: str) -> Path:
    """변수: 사용자 PDF 경로. 원리: resolve 뒤 private_benchmarks 밖의 저작권 원문 접근을 막는다."""
    path = Path(value).resolve()
    if PRIVATE_ROOT != path and PRIVATE_ROOT not in path.parents:
        raise argparse.ArgumentTypeError("입력 PDF는 private_benchmarks 하위여야 합니다.")
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise argparse.ArgumentTypeError("존재하는 PDF 파일이 필요합니다.")
    return path


def _extract_question_blocks(pdf_path: Path) -> list[dict[str, object]]:
    """변수: PDF 경로. 원리: 페이지 텍스트를 합친 뒤 줄 시작 문항 번호를 기준으로 1~30 블록을 추출한다."""
    with fitz.open(pdf_path) as document:
        text = "\n".join(page.get_text("text") for page in document)
    matches = list(QUESTION_BOUNDARY.finditer(text))
    blocks: list[dict[str, object]] = []
    seen: set[int] = set()
    for index, match in enumerate(matches):
        number = int(match.group("number"))
        if number in seen:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        question = text[match.start():end].strip()
        if len(question) < 12:
            continue
        seen.add(number)
        blocks.append({"question_number": number, "question": question})
    return blocks


def diagnose(pdf_path: Path) -> dict[str, object]:
    """변수: 비공개 PDF. 원리: 각 문항 블록의 분류·실행 결과를 모아 직접 입력 가능률과 실패 이유를 계산한다."""
    cases: list[dict[str, object]] = []
    for block in _extract_question_blocks(pdf_path):
        parsed = classify(str(block["question"]))
        result = solve_rule(str(parsed.get("domain", "")), dict(parsed.get("slots", {})))
        cases.append({
            "question_number": block["question_number"],
            "domain": parsed.get("domain"),
            "status": result.get("status"),
            "answer": result.get("answer"),
            "verified": result.get("verified", False),
            "reason": result.get("reason", ""),
            "input_preview": str(block["question"])[:180],
        })
    pass_count = sum(case["status"] == "PASS" and case["verified"] is True for case in cases)
    return {
        "kind": "raw_pdf_engine_ingestion_diagnostic",
        "warning": "정답표 대조 전 결과입니다. pass_rate는 정답 정확도가 아니라 원문을 그대로 실행한 비율입니다.",
        "pdf": pdf_path.name,
        "extracted_questions": len(cases),
        "direct_execution_passed": pass_count,
        "direct_execution_rate": pass_count / len(cases) if cases else 0.0,
        "cases": cases,
    }


def main() -> int:
    """변수: 입력 PDF·출력 JSON. 원리: 진단 결과를 UTF-8 JSON으로 private 경로에만 저장한다."""
    parser = argparse.ArgumentParser(description="실제 PDF의 현재 엔진 직접 입력 가능률을 진단합니다.")
    parser.add_argument("--pdf", type=_private_file, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if PRIVATE_ROOT != output and PRIVATE_ROOT not in output.parents:
        raise ValueError("결과 경로는 private_benchmarks 하위여야 합니다.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(diagnose(args.pdf), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
