"""LaTeX 정규화 뒤 세 라우터를 통해 공통 수학 도구를 실행하는 오케스트레이터."""
from __future__ import annotations

from typing import Any

from latex_normalizer import normalize_latex_input
from rule_based_nlp import build_solution_trace, parse_for_domain, solve_rule
from tool_routing import has_minimum_evidence, rank_tools


ROUTER_VERSIONS = {
    "rule": "rule-router-v1",
    "neural": "mini-neural-profile-v1",
    "embedding": "local-e5-prototype-router-v1 (fallback: char-ngram-v1)",
}


def solve_with_router(question: str, mode: str = "rule", candidate_limit: int = 12) -> dict[str, Any]:
    """변수: 문제 원문·라우터 방식·후보 수. 원리: 같은 슬롯 파서·solver·검산기로 후보를 순서대로 실행한다.

    첫 PASS도 반드시 도구의 verified 불변식을 만족해야 반환한다. 따라서 라우터가
    틀린 후보를 앞에 두더라도 계산 실패를 정답처럼 노출하지 않는다.
    """
    latex = normalize_latex_input(question)
    if latex["unsupported"]:
        return {
            "status": "FAIL", "question": latex["original"], "normalized_question": latex["normalized"],
            "router": {"mode": mode, "version": ROUTER_VERSIONS.get(mode)},
            "reason": f"지원하지 않는 LaTeX 명령: {', '.join(latex['unsupported'])}", "candidates": [],
        }
    candidates = rank_tools(latex["normalized"], mode, candidate_limit)
    attempts: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate["score"] <= 0:
            continue
        if not has_minimum_evidence(latex["normalized"], candidate["domain"]):
            attempts.append({"domain": candidate["domain"], "score": candidate["score"], "slots": {}, "status": "SKIP", "reason": "도메인 최소 증거가 부족합니다."})
            continue
        parsed = parse_for_domain(latex["normalized"], candidate["domain"])
        result = solve_rule(candidate["domain"], parsed["slots"])
        attempts.append({"domain": candidate["domain"], "score": candidate["score"], "slots": parsed["slots"], "status": result.get("status"), "reason": result.get("reason", "")})
        if result.get("status") == "PASS" and result.get("verified") is True:
            parsed["router"] = {"mode": mode, "version": ROUTER_VERSIONS[mode], "selected_domain": candidate["domain"], "score": candidate["score"]}
            return {
                "status": "PASS", "question": latex["original"], "normalized_question": latex["normalized"],
                "parse": parsed, "router": parsed["router"], "candidates": candidates,
                "attempts": attempts, "result": result, "steps": build_solution_trace(parsed, result),
            }
    return {
        "status": "FAIL", "question": latex["original"], "normalized_question": latex["normalized"],
        "router": {"mode": mode, "version": ROUTER_VERSIONS.get(mode)}, "candidates": candidates,
        "attempts": attempts, "reason": "후보 도구가 필수 슬롯·적용 조건·독립 검산을 함께 통과하지 못했습니다.",
    }
