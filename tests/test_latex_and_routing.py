"""LaTeX 입력과 세 도구 라우터가 같은 계산·검산 경로를 공유하는지 검증한다."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from experiment_runner import evaluate_router, validate_private_records  # noqa: E402
from latex_normalizer import normalize_latex_input  # noqa: E402
from solver_router import solve_with_router  # noqa: E402


def test_core_latex_forms_are_normalized() -> None:
    """분수·극한·정적분의 핵심 LaTeX가 기존 슬롯 파서가 읽는 평문으로 변환되는지 확인한다."""
    assert normalize_latex_input(r"\frac{1}{2}")["normalized"] == "1/2"
    assert normalize_latex_input(r"\lim_{x\to 3}x^2")["normalized"] == "lim x->3x^2"
    assert normalize_latex_input(r"\int_0^2 x^1 dx")["normalized"] == "정적분 0부터 2 x^1 dx"
    assert normalize_latex_input(r"\log_3 2\times\log_4 a=2")["normalized"] == "log_3 2*log_4 a=2"


def test_all_router_modes_solve_same_latex_cases() -> None:
    """동일 LaTeX 문항이 rule·neural·embedding에서 같은 검산 정답으로 끝나는지 확인한다."""
    cases = [(r"$2x+3=9$", 3), (r"지수방정식 $2^x=16$", 4), (r"$5^{x+4}=25^{2x-4}$", 4), (r"$\log_3 2\times\log_4 a=2$", 81), (r"$\lim_{x\to 3}x^2+3x$", 18), (r"$\int_0^2 x^1 dx$", 2)]
    for mode in ("rule", "neural", "embedding"):
        for question, expected in cases:
            response = solve_with_router(question, mode)
            assert response["status"] == "PASS"
            assert response["result"]["answer"] == expected
            assert response["result"]["verified"] is True


def test_unsupported_latex_is_rejected() -> None:
    """지원하지 않는 aligned 환경은 추측 풀이 대신 재현 가능한 FAIL을 반환하는지 확인한다."""
    response = solve_with_router(r"\begin{aligned}x&=1\end{aligned}", "rule")
    assert response["status"] == "FAIL"
    assert "지원하지 않는 LaTeX" in response["reason"]


def test_horner_tool_is_selected_and_verified_by_all_routers() -> None:
    """새 범용 다항식 도구가 후보 선택·슬롯 추출·독립 계산을 모두 통과하는지 확인한다."""
    for mode in ("rule", "neural", "embedding"):
        response = solve_with_router("P(x)=2x^3-3x+1; P(2)", mode)
        assert response["status"] == "PASS"
        assert response["router"]["selected_domain"] == "hs_polynomial_value"
        assert response["result"]["answer"] == 11
        assert response["result"]["verified"] is True


def test_integer_gcd_tool_is_selected_and_verified_by_all_routers() -> None:
    """정수론 지식 계약과 유클리드 호제법 도구가 세 라우터에서 함께 실행되는지 확인한다."""
    for mode in ("rule", "neural", "embedding"):
        response = solve_with_router("gcd(84,30)", mode)
        assert response["status"] == "PASS"
        assert response["router"]["selected_domain"] == "integer_gcd"
        assert response["result"]["answer"] == 6
        assert response["result"]["verified"] is True


def test_exponential_asymptote_distance_tool_is_shared() -> None:
    """지수함수의 수평 점근선 거리 문제를 세 라우터가 같은 범용 도구로 검산하는지 확인한다."""
    question = "곡선 y=2^x 위의 점 (a,b)와 곡선 y=2^x-3의 점근선 사이의 거리가 7일 때, a+b의 값"
    for mode in ("rule", "neural", "embedding"):
        response = solve_with_router(question, mode)
        assert response["status"] == "PASS"
        assert response["router"]["selected_domain"] == "hs_exponential_asymptote_distance"
        assert response["result"]["answer"] == 6
        assert response["result"]["verified"] is True


def test_inverse_log_power_coordinate_tool_is_shared() -> None:
    """로그 역함수의 좌표 거듭제곱 문제를 세 라우터가 같은 도구로 계산·검산하는지 확인한다."""
    question = r"함수 $y=\log_5 x+2$의 역함수의 그래프가 점 $(4,5^k)$를 지날 때, k의 값"
    for mode in ("rule", "neural", "embedding"):
        response = solve_with_router(question, mode)
        assert response["status"] == "PASS"
        assert response["router"]["selected_domain"] == "hs_inverse_log_power_coordinate"
        assert response["result"]["answer"] == 2
        assert response["result"]["verified"] is True


def test_experiment_metrics_separate_false_pass_and_rejection() -> None:
    """실험 보고서가 정답 정확도·허위 PASS·미지원 거부를 독립 지표로 집계하는지 확인한다."""
    records = [
        {"case_id": "latex-linear", "question": r"$2x+3=9$", "expected": 3, "expected_domain": "cm_linear", "supported": True},
        {"case_id": "unsupported", "question": r"\begin{aligned}x&=1\end{aligned}", "expected": None, "expected_domain": None, "supported": False},
    ]
    report = evaluate_router(records, "rule")
    assert report["tool_selection_accuracy"] == 1.0
    assert report["answer_accuracy"] == 1.0
    assert report["false_pass_rate"] == 0.0
    assert report["unsupported_rejection_accuracy"] == 1.0


def test_private_corpus_contract_requires_full_metadata() -> None:
    """실제 기출 코퍼스는 문제 전문·LaTeX·정답·출처·지원 범위를 빠짐없이 제공해야 한다."""
    valid = [{"case_id": "official-01", "source": "local", "source_document_sha256": "sha256:test", "question_number": 1,
              "question": "2x+3=9", "latex_question": "$2x+3=9$", "expected": 3, "expected_domain": "cm_linear",
              "curriculum": "고등학교", "diagram_dependent": False, "supported": True}]
    validate_private_records(valid)
    invalid = [dict(valid[0], latex_question="")]
    try:
        validate_private_records(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("LaTeX 전문이 없는 실제 코퍼스는 거부해야 합니다.")


if __name__ == "__main__":
    test_core_latex_forms_are_normalized()
    test_all_router_modes_solve_same_latex_cases()
    test_unsupported_latex_is_rejected()
    test_horner_tool_is_selected_and_verified_by_all_routers()
    test_integer_gcd_tool_is_selected_and_verified_by_all_routers()
    test_exponential_asymptote_distance_tool_is_shared()
    test_inverse_log_power_coordinate_tool_is_shared()
    test_private_corpus_contract_requires_full_metadata()
    test_experiment_metrics_separate_false_pass_and_rejection()
    print("PASS: latex and routing")
