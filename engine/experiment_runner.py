"""세 도구 라우터를 동일한 실제 문제 코퍼스로 비교하는 재현 가능한 평가기."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from solver_router import ROUTER_VERSIONS, solve_with_router


PRIVATE_CORPUS_REQUIRED_FIELDS = (
    "case_id", "source", "source_document_sha256", "question_number", "question", "latex_question",
    "expected", "curriculum", "diagram_dependent", "supported",
)


def validate_private_records(records: list[dict[str, Any]]) -> None:
    """변수: 비공개 기출 레코드 배열. 원리: 전문·LaTeX·출처·정답·그림 의존 메타데이터 누락을 실행 전에 거부한다."""
    if not isinstance(records, list) or not records:
        raise ValueError("실전 코퍼스는 비어 있지 않은 JSON 배열이어야 합니다.")
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or any(field not in record for field in PRIVATE_CORPUS_REQUIRED_FIELDS):
            raise ValueError("실전 코퍼스 레코드에 필수 메타데이터가 없습니다.")
        case_id = str(record["case_id"])
        if not case_id or case_id in seen or not str(record["question"]).strip() or not str(record["latex_question"]).strip():
            raise ValueError("실전 코퍼스의 case_id·문제 전문·LaTeX는 유일하고 비어 있지 않아야 합니다.")
        if not isinstance(record["question_number"], int) or record["question_number"] < 1 or not isinstance(record["diagram_dependent"], bool) or not isinstance(record["supported"], bool):
            raise ValueError("문항 번호·그림 의존·지원 여부의 자료형이 올바르지 않습니다.")
        if record["supported"] and not str(record.get("expected_domain", "")).strip():
            raise ValueError("지원 문항에는 expected_domain이 필요합니다.")
        seen.add(case_id)


def _same_answer(actual: Any, expected: Any) -> bool:
    """변수: 실제 반환값·정답지 값. 원리: 정확한 동치 후 수치 오차만 제한적으로 허용한다."""
    if actual == expected:
        return True
    try:
        return abs(float(actual) - float(expected)) < 1e-9
    except (TypeError, ValueError):
        return False


def _response_signature(response: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    """변수: 한 번의 solver 응답. 원리: 시간·trace를 제외한 결정적 풀이 결과만 비교 가능한 튜플로 축약한다."""
    return (
        response.get("status"), response.get("router", {}).get("selected_domain"),
        response.get("result", {}).get("answer"), response.get("result", {}).get("verified"),
    )


def _metric_summary(cases: list[dict[str, Any]]) -> dict[str, float | None]:
    """변수: 평가 결과 행. 원리: 지원·미지원 집합을 분리해 정확도와 허위 PASS를 같은 분모 규칙으로 집계한다."""
    routed = [case for case in cases if case["expected_domain"]]
    supported_cases = [case for case in cases if case["supported"]]
    unsupported_cases = [case for case in cases if not case["supported"]]
    rate = lambda values: sum(values) / len(values) if values else None
    return {
        "tool_selection_accuracy": rate([case["selected_domain"] == case["expected_domain"] for case in routed]),
        "answer_accuracy": rate([case["answer_ok"] for case in supported_cases]),
        "verification_pass_rate": rate([case["verified"] for case in supported_cases]),
        "false_pass_rate": rate([case["false_pass"] for case in cases]),
        "unsupported_rejection_accuracy": rate([case["unsupported_rejected"] for case in unsupported_cases]),
        "deterministic_pass_rate": rate([case["deterministic"] for case in cases]),
        "mean_elapsed_ms": rate([case["elapsed_ms"] for case in cases]),
    }


def evaluate_router(records: list[dict[str, Any]], mode: str, repeats: int = 2) -> dict[str, Any]:
    """변수: 전문 코퍼스·라우터·반복 수. 원리: 공통 solver 결과를 반복해 정답·검산·거부·결정성·단원별 지표를 분리 집계한다."""
    if repeats < 1:
        raise ValueError("반복 수는 1 이상이어야 합니다.")
    cases: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        started = time.perf_counter()
        response = solve_with_router(str(record.get("question", "")), mode)
        signatures = [_response_signature(response)] + [_response_signature(solve_with_router(str(record.get("question", "")), mode)) for _ in range(repeats - 1)]
        elapsed_ms = round((time.perf_counter() - started) * 1000 / repeats, 3)
        expected = record.get("expected")
        expected_domain = record.get("expected_domain")
        supported = bool(record.get("supported", expected_domain is not None))
        selected = response.get("router", {}).get("selected_domain")
        passed = response.get("status") == "PASS"
        answer_ok = passed and _same_answer(response.get("result", {}).get("answer"), expected)
        cases.append({
            "case_id": record.get("case_id", f"case-{index:04d}"), "source": record.get("source", "local-private"),
            "question_hash": record.get("question_hash"), "expected_domain": expected_domain, "selected_domain": selected,
            "curriculum": record.get("curriculum", "미분류"), "supported": supported, "status": response.get("status"), "answer_ok": answer_ok,
            "verified": response.get("result", {}).get("verified") is True, "false_pass": passed and not answer_ok,
            "unsupported_rejected": not supported and not passed, "deterministic": len(set(signatures)) == 1, "elapsed_ms": elapsed_ms,
            "reason": response.get("reason", response.get("result", {}).get("reason", "")),
        })
    by_curriculum = {unit: _metric_summary([case for case in cases if case["curriculum"] == unit]) for unit in sorted({str(case["curriculum"]) for case in cases})}
    return {"router": {"mode": mode, "version": ROUTER_VERSIONS[mode]}, "repeats": repeats, "total": len(cases), "cases": cases, "by_curriculum": by_curriculum, **_metric_summary(cases)}


def run_experiment(path: str | Path, repeats: int = 2) -> dict[str, Any]:
    """변수: UTF-8 JSON 코퍼스 경로·반복 수. 원리: 정확히 같은 전문 문항으로 세 라우터의 결정적 보고서를 만든다."""
    source = Path(path)
    records = json.loads(source.read_text(encoding="utf-8"))
    validate_private_records(records)
    return {"source": str(source), "repeats": repeats, "reports": [evaluate_router(records, mode, repeats) for mode in ("rule", "neural", "embedding")]}
