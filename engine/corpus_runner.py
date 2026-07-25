"""사용자 제공 문제 코퍼스를 읽어 풀이·정답·검산을 일괄 평가한다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rule_based_nlp import build_solution_trace, classify, select_optimal_rule, solve_rule


def _same_answer(actual: Any, expected: Any) -> bool:
    """문자·정수·실수 정답을 안전하게 비교한다."""
    if actual == expected:
        return True
    try:
        return abs(float(actual) - float(expected)) < 1e-9
    except (TypeError, ValueError):
        return False


def run_corpus(path: str | Path) -> dict[str, Any]:
    """필요 변수: UTF-8 JSON/JSONL 경로. 작동 원리: 각 문항을 독립적으로 분류·계산·검산한다."""
    source = Path(path)
    raw = source.read_text(encoding="utf-8").strip()
    records = json.loads(raw) if source.suffix.lower() == ".json" else [json.loads(line) for line in raw.splitlines() if line.strip()]
    cases: list[dict[str, Any]] = []
    for index, item in enumerate(records, start=1):
        question = str(item.get("question", "")).strip()
        parsed = classify(question)
        result = solve_rule(parsed.get("domain", ""), parsed.get("slots", {}))
        expected = item.get("expected")
        passed = result.get("status") == "PASS" and _same_answer(result.get("answer"), expected) and result.get("verified") is True
        cases.append({
            "case_id": item.get("case_id", f"corpus-{index:04d}"),
            "source_label": item.get("source_label", "user_corpus"),
            "curriculum": item.get("curriculum", "미지정"),
            "question": question,
            "expected": expected,
            "answer": result.get("answer"),
            "status": "PASS" if passed else "FAIL",
            "domain": parsed.get("domain"),
            "rule_path": select_optimal_rule(parsed).get("path", []),
            "formula": result.get("formula", ""),
            "reason": result.get("reason", ""),
            "verified": result.get("verified", False),
            "trace": build_solution_trace(parsed, result) if result.get("status") == "PASS" else [],
        })
    passed_count = sum(case["status"] == "PASS" for case in cases)
    return {"source": str(source), "total": len(cases), "passed": passed_count, "failed": len(cases) - passed_count, "pass_rate": passed_count / len(cases) if cases else 0.0, "cases": cases}


def main() -> int:
    """명령행 코퍼스를 실행하고 결과 JSON을 저장한다."""
    parser = argparse.ArgumentParser(description="AIFlow-Core 문제 코퍼스 검증")
    parser.add_argument("corpus")
    parser.add_argument("--output", default="docs/corpus_validation_report.json")
    args = parser.parse_args()
    report = run_corpus(args.corpus)
    output = Path(args.output)
    if not output.is_absolute():
        output = Path(__file__).resolve().parents[1] / output
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SUMMARY passed={report['passed']} total={report['total']} rate={report['pass_rate']:.3f}")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
