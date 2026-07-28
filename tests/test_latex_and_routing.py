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


def test_indexed_root_latex_and_rational_power_route() -> None:
    """LaTeX n제곱근과 유리수 지수가 공통 지수 슬롯·검산 결과로 이어지는지 확인한다."""
    normalized = normalize_latex_input(r"\sqrt[3]{9}\times3^{-5/3}")
    assert normalized["normalized"] == "root_3(9)*3^(-5/3)"
    result = solve_with_router(r"\sqrt[3]{9}\times3^{-5/3}", "rule")
    assert result["status"] == "PASS"
    assert abs(result["result"]["answer"] - 1 / 3) < 1e-12
    assert result["result"]["verified"] is True


def test_all_router_modes_solve_same_latex_cases() -> None:
    """동일 LaTeX 문항이 rule·neural·embedding에서 같은 검산 정답으로 끝나는지 확인한다."""
    cases = [(r"$2x+3=9$", 3), (r"지수방정식 $2^x=16$", 4), (r"$5^{x+4}=25^{2x-4}$", 4), (r"$\log_3 2\times\log_4 a=2$", 81), (r"$\lim_{x\to 3}x^2+3x$", 18), (r"$\int_0^2 x^1 dx$", 2)]
    for mode in ("rule", "neural", "embedding"):
        for question, expected in cases:
            response = solve_with_router(question, mode)
            assert response["status"] == "PASS"
            assert response["result"]["answer"] == expected
            assert response["result"]["verified"] is True


def test_factored_polynomial_derivative_is_shared_by_all_routers() -> None:
    """일차식×이차식 다항식의 도함수값은 세 라우터가 같은 슬롯·독립 차분 검산으로 계산한다."""
    question = "함수 f(x)=(3x-1)(x^2-2x+2)에 대하여 f'(2)의 값을 구하시오."
    for mode in ("rule", "neural", "embedding"):
        response = solve_with_router(question, mode)
        assert response["status"] == "PASS"
        assert response["router"]["selected_domain"] == "hs2_derivative"
        assert response["result"]["answer"] == 16
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


def test_polynomial_addition_tool_is_shared_for_text_and_latex() -> None:
    """다항식 덧셈은 평문·LaTeX에서 차수별 동일 계수와 표준형 정답으로 끝나는지 확인한다."""
    cases = [
        "두 다항식 A=2x^2+3x-1, B=-x^2-2x+3에 대하여 A+B를 간단히 하여라.",
        r"$A=2x^2+3x-1,\;B=-x^2-2x+3$에 대하여 $A+B$를 간단히 하여라.",
    ]
    for mode in ("rule", "neural", "embedding"):
        for question in cases:
            response = solve_with_router(question, mode)
            assert response["status"] == "PASS"
            assert response["router"]["selected_domain"] == "hs_polynomial_addition"
            assert response["result"]["answer"] == "x^2+x+2"
            assert response["result"]["verified"] is True


def test_integer_gcd_tool_is_selected_and_verified_by_all_routers() -> None:
    """정수론 지식 계약과 유클리드 호제법 도구가 세 라우터에서 함께 실행되는지 확인한다."""
    for mode in ("rule", "neural", "embedding"):
        response = solve_with_router("gcd(84,30)", mode)
        assert response["status"] == "PASS"
        assert response["router"]["selected_domain"] == "integer_gcd"
        assert response["result"]["answer"] == 6
        assert response["result"]["verified"] is True


def test_absolute_linear_equation_is_shared_and_blocks_linear_false_pass() -> None:
    """절댓값 일차방정식은 평문·LaTeX에서 두 해를 모두 재대입하고, 일반 일차식의 한 해 허위 PASS를 막아야 한다."""
    cases = ["절댓값 방정식 |2x-3|=5의 해", r"절댓값 방정식 $\left|2x-3\right|=5$의 해"]
    for mode in ("rule", "neural", "embedding"):
        for question in cases:
            response = solve_with_router(question, mode)
            assert response["status"] == "PASS"
            assert response["router"]["selected_domain"] == "hs_absolute_linear_equation"
            assert response["result"]["answer"] == [-1, 4]
            assert response["result"]["verified"] is True
    for mode in ("rule", "neural", "embedding"):
        response = solve_with_router("|2x-3|=-5", mode)
        assert response["status"] == "FAIL"
        assert all(not (attempt["domain"] == "cm_linear" and attempt["status"] == "PASS") for attempt in response["attempts"])


def test_linear_inequality_is_shared_and_reverses_negative_coefficient() -> None:
    """일차부등식은 평문·LaTeX에서 같은 경계값에 도달하고 음수 계수일 때만 방향을 뒤집어야 한다."""
    cases = [
        ("부등식 -2x+3<=7의 해집합", "≥", -2),
        (r"부등식 $3x-1>5$의 해집합", ">", 2),
    ]
    for mode in ("rule", "neural", "embedding"):
        for question, relation, boundary in cases:
            response = solve_with_router(question, mode)
            assert response["status"] == "PASS"
            assert response["router"]["selected_domain"] == "fn_linear_inequality"
            assert response["result"]["parameters"] == {"boundary": boundary, "relation": relation}
            assert response["result"]["verified"] is True
            assert all(not (attempt["domain"] == "cm_linear" and attempt["status"] == "PASS") for attempt in response["attempts"])
    # 여러 비교 조건을 가진 함수 문장은 단일 부등식 도구가 임의로 분리해 풀면 안 된다.
    composite = "함수 g(x)=x^2 (0<=x<3)이고 모든 x>=0에서 조건을 만족한다."
    for mode in ("rule", "neural", "embedding"):
        response = solve_with_router(composite, mode)
        assert response["status"] == "FAIL"
        assert all(not (attempt["domain"] == "fn_linear_inequality" and attempt["status"] == "PASS") for attempt in response["attempts"])


def test_three_dimensional_dot_product_is_shared_for_text_and_latex() -> None:
    """공간벡터 내적은 점곱·LaTeX 곱 기호 모두에서 동일한 세 성분 슬롯과 검산 정답을 반환해야 한다."""
    cases = [
        "공간벡터 (1,2,3)·(2,-1,0)의 내적",
        r"$\left(1,2,3\right)\cdot\left(2,-1,0\right)$의 내적",
    ]
    for mode in ("rule", "neural", "embedding"):
        for question in cases:
            response = solve_with_router(question, mode)
            assert response["status"] == "PASS"
            assert response["router"]["selected_domain"] == "csg_vector_dot_3d"
            assert response["parse"]["slots"] == {"vector_a": [1, 2, 3], "vector_b": [2, -1, 0]}
            assert response["result"]["answer"] == 0
            assert response["result"]["verified"] is True


def test_numeric_matrix_product_is_shared_for_text_and_latex() -> None:
    """명시적 2×2 정수 행렬곱은 평문·LaTeX에서 같은 행렬 슬롯과 성분별 검산 결과를 반환해야 한다."""
    cases = [
        "행렬곱 A=((1,2),(3,4)), B=((2,0),(-1,5))",
        r"$A=\begin{pmatrix}1&2\\3&4\end{pmatrix}, B=\begin{pmatrix}2&0\\-1&5\end{pmatrix}$의 행렬곱",
    ]
    for mode in ("rule", "neural", "embedding"):
        for question in cases:
            response = solve_with_router(question, mode)
            assert response["status"] == "PASS"
            assert response["router"]["selected_domain"] == "la_matrix_multiply"
            assert response["result"]["answer"] == [[0, 10], [2, 20]]
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


def test_log_interval_extrema_tool_is_shared_for_text_and_latex() -> None:
    """로그함수의 구간 극값 문제는 평문·LaTeX가 세 라우터에서 같은 슬롯과 정답으로 끝나는지 확인한다."""
    cases = [
        "4<=x<=11에서 함수 f(x)=log_2(x-3)+5의 최댓값과 최솟값의 합",
        r"$4\le x\le11,\;f(x)=\log_2(x-3)+5$의 최댓값과 최솟값의 합",
    ]
    for mode in ("rule", "neural", "embedding"):
        for question in cases:
            response = solve_with_router(question, mode)
            assert response["status"] == "PASS"
            assert response["router"]["selected_domain"] == "hs_log_interval_extrema"
            assert response["result"]["answer"] == 13
            assert response["result"]["verified"] is True


def test_sine_linear_interval_tool_is_shared_for_text_and_latex() -> None:
    """특수각 사인 방정식은 평문·LaTeX에서 같은 유일 구간해와 검산 결과에 도달해야 한다."""
    cases = [
        "pi/2<=x<=3pi/2일 때 방정식 2sin x+sqrt(3)=0을 만족시키는 x의 값",
        r"$\frac{\pi}{2}\le x\le\frac{3\pi}{2},\;2\sin x+\sqrt{3}=0$",
    ]
    for mode in ("rule", "neural", "embedding"):
        for question in cases:
            response = solve_with_router(question, mode)
            assert response["status"] == "PASS"
            assert response["router"]["selected_domain"] == "hs_sine_linear_interval"
            assert response["result"]["answer"] == "4π/3"
            assert response["result"]["verified"] is True


def test_arithmetic_sequence_sum_contract_is_shared_for_text_and_latex() -> None:
    """승격한 등차수열 합 계약은 평문·LaTeX가 동일한 슬롯·정답·검산으로 끝나야 한다."""
    cases = [
        "등차수열 첫항 2, 공차 3의 첫 5항의 합",
        r"등차수열에서 $a_1=2,d=3$일 때 첫 5항의 합",
    ]
    for mode in ("rule", "neural", "embedding"):
        for question in cases:
            response = solve_with_router(question, mode)
            assert response["status"] == "PASS"
            assert response["router"]["selected_domain"] == "cm_arith_sequence"
            assert response["result"]["answer"] == 40
            assert response["result"]["verified"] is True


def test_nonunique_sine_interval_is_rejected_without_unrelated_pass() -> None:
    """특수각 해가 둘 이상인 구간은 다른 숫자 파서의 우연한 PASS 없이 세 라우터가 거부해야 한다."""
    question = "0<=x<=2pi에서 2sin x+sqrt(3)=0을 만족시키는 x의 값"
    for mode in ("rule", "neural", "embedding"):
        response = solve_with_router(question, mode)
        assert response["status"] == "FAIL"
        assert all(attempt["domain"] != "hs2_integral" or attempt["status"] != "PASS" for attempt in response["attempts"])


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
    assert report["deterministic_pass_rate"] == 1.0
    assert report["by_curriculum"]["미분류"]["answer_accuracy"] == 1.0


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
    test_indexed_root_latex_and_rational_power_route()
    test_all_router_modes_solve_same_latex_cases()
    test_factored_polynomial_derivative_is_shared_by_all_routers()
    test_unsupported_latex_is_rejected()
    test_horner_tool_is_selected_and_verified_by_all_routers()
    test_polynomial_addition_tool_is_shared_for_text_and_latex()
    test_integer_gcd_tool_is_selected_and_verified_by_all_routers()
    test_absolute_linear_equation_is_shared_and_blocks_linear_false_pass()
    test_linear_inequality_is_shared_and_reverses_negative_coefficient()
    test_three_dimensional_dot_product_is_shared_for_text_and_latex()
    test_numeric_matrix_product_is_shared_for_text_and_latex()
    test_exponential_asymptote_distance_tool_is_shared()
    test_inverse_log_power_coordinate_tool_is_shared()
    test_log_interval_extrema_tool_is_shared_for_text_and_latex()
    test_sine_linear_interval_tool_is_shared_for_text_and_latex()
    test_arithmetic_sequence_sum_contract_is_shared_for_text_and_latex()
    test_nonunique_sine_interval_is_rejected_without_unrelated_pass()
    test_private_corpus_contract_requires_full_metadata()
    test_experiment_metrics_separate_false_pass_and_rejection()
    print("PASS: latex and routing")
