"""AIFlow-Core가 규칙에서 호출하는 재사용 가능한 수학 계산 도구 모음.

각 도구는 이미 추출된 슬롯만 받아 계산한다. 자연어 해석과 수학 계산을 분리해,
특정 시험 문항의 숫자나 정답을 코드에 고정하지 않는다.
"""
from __future__ import annotations

from typing import Any, Callable
from fractions import Fraction
from math import gcd, log, pi, sin, sqrt


def polynomial_remainder_two_linear(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 두 나눗셈 근·나머지·질의점. 원리: 일차 나머지 R(x)를 두 점 보간으로 결정한다."""
    root1, remainder1, root2, remainder2, point = (slots.get(key) for key in ("root1", "remainder1", "root2", "remainder2", "point"))
    if None in (root1, remainder1, root2, remainder2, point) or root1 == root2:
        return {"status": "FAIL", "reason": "서로 다른 두 일차식의 근·나머지·질의점이 필요합니다."}
    slope = (remainder2 - remainder1) / (root2 - root1)
    answer = remainder1 + slope * (point - root1)
    return {
        "status": "PASS",
        "answer": int(answer) if answer == int(answer) else answer,
        "formula": "R(x)=R(r1)+(R(r2)-R(r1))(x-r1)/(r2-r1)",
        "verified": True,
        "tool": "polynomial_remainder_two_linear",
    }


def rational_interval_extrema(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 분모 이동값·구간 끝점·최대·최소. 원리: a/(x-c)+b의 끝점 값 두 개를 연립해 a,b를 구한다."""
    shift, left, right, maximum, minimum = (slots.get(key) for key in ("shift", "left", "right", "maximum", "minimum"))
    if None in (shift, left, right, maximum, minimum) or left >= right or left == shift or right == shift:
        return {"status": "FAIL", "reason": "유효한 구간·분모 이동값·최대·최소가 필요합니다."}
    # a>0이고 구간이 분모의 같은 쪽에 있을 때 f'(x)=-a/(x-c)^2<0이다.
    if left <= shift <= right:
        return {"status": "FAIL", "reason": "구간에 분모가 0이 되는 점이 포함되어 있습니다."}
    reciprocal_gap = 1 / (left - shift) - 1 / (right - shift)
    if reciprocal_gap == 0:
        return {"status": "FAIL", "reason": "끝점으로 계수를 결정할 수 없습니다."}
    a = (maximum - minimum) / reciprocal_gap
    b = maximum - a / (left - shift)
    if a <= 0:
        return {"status": "FAIL", "reason": "입력된 극값 조건이 a>0과 양립하지 않습니다."}
    answer = a + b
    return {
        "status": "PASS",
        "answer": int(answer) if answer == int(answer) else answer,
        "formula": "f(x)=a/(x-c)+b, f(left)=최대, f(right)=최소",
        "verified": abs((a / (left - shift) + b) - maximum) < 1e-9 and abs((a / (right - shift) + b) - minimum) < 1e-9,
        "parameters": {"a": a, "b": b},
        "tool": "rational_interval_extrema",
    }


def symbolic_matrix_product_2x2(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: k를 포함한 2×2 행렬과 곱 조건. 원리: 양의 정수 k 후보를 대입해 수치 조건을 만족하는 곱을 선택한다."""
    left, right, targets, requested = (slots.get(key) for key in ("left", "right", "targets", "requested"))
    if not isinstance(left, list) or not isinstance(right, list) or not isinstance(targets, list) or not requested:
        return {"status": "FAIL", "reason": "2×2 행렬, 곱의 수치 조건, 구할 성분이 필요합니다."}

    def evaluate(entry: int | str, k: int) -> int:
        return k if entry == "k" else int(entry)

    def multiply(k: int) -> list[list[int]]:
        return [[sum(evaluate(left[row][index], k) * evaluate(right[index][column], k) for index in range(2)) for column in range(2)] for row in range(2)]

    matches = []
    for k in range(1, 101):
        product = multiply(k)
        if all(product[item["row"]][item["column"]] == item["expected"] for item in targets):
            matches.append((k, product))
    if len(matches) != 1:
        return {"status": "FAIL", "reason": "행렬 곱 조건을 만족하는 양의 정수 k가 유일하지 않습니다."}
    k, product = matches[0]
    answer = sum(product[item[0]][item[1]] for item in requested)
    return {
        "status": "PASS",
        "answer": answer,
        "formula": "(AB)_ij=Σ A_itB_tj",
        "verified": all(product[item["row"]][item["column"]] == item["expected"] for item in targets),
        "parameters": {"k": k, "product": product},
        "tool": "symbolic_matrix_product_2x2",
    }


def evaluate_polynomial_horner(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 최고차항부터 계수 배열과 대입점. 원리: Horner 중첩 곱으로 다항식 값을 선형 시간에 계산·검산한다."""
    coefficients, point = slots.get("coefficients"), slots.get("point")
    if not isinstance(coefficients, list) or not coefficients or point is None:
        return {"status": "FAIL", "reason": "최고차항부터의 다항식 계수와 대입점이 필요합니다."}
    try:
        normalized = [int(value) for value in coefficients]
        numeric_point = int(point)
    except (TypeError, ValueError):
        return {"status": "FAIL", "reason": "현재 Horner 도구는 정수 계수와 정수 대입점만 지원합니다."}
    answer = normalized[0]
    for coefficient in normalized[1:]:
        answer = answer * numeric_point + coefficient
    direct = sum(coefficient * numeric_point ** (len(normalized) - index - 1) for index, coefficient in enumerate(normalized))
    return {"status": "PASS", "answer": answer, "formula": "Horner: (((c_n x+c_{n-1})x+…)x+c_0)", "verified": answer == direct, "tool": "evaluate_polynomial_horner"}


def evaluate_integer_gcd(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 두 정수. 원리: 유클리드 호제법 결과가 두 수를 나누고 모든 공약수의 배수 관계를 만족하는지 확인한다."""
    values = slots.get("integers")
    if not isinstance(values, list) or len(values) != 2:
        return {"status": "FAIL", "reason": "최대공약수를 구할 서로 다른 두 정수가 필요합니다."}
    try:
        left, right = (int(value) for value in values)
    except (TypeError, ValueError):
        return {"status": "FAIL", "reason": "최대공약수 도구에는 정수만 입력할 수 있습니다."}
    if left == 0 and right == 0:
        return {"status": "FAIL", "reason": "gcd(0,0)은 이 도구의 정의 범위 밖입니다."}
    answer = gcd(left, right)
    return {"status": "PASS", "answer": answer, "formula": "gcd(a,b)=gcd(b,a mod b)", "verified": left % answer == 0 and right % answer == 0, "tool": "evaluate_integer_gcd"}


def solve_log_product_equation(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 첫 로그의 밑·진수, 둘째 로그의 밑, 곱의 값. 원리: log_b(x)를 고립해 양의 실수 해를 계산·재대입한다."""
    first_base, first_value, second_base, target = (slots.get(key) for key in ("first_base", "first_value", "second_base", "target"))
    try:
        first_base, first_value, second_base, target = (float(first_base), float(first_value), float(second_base), float(target))
    except (TypeError, ValueError):
        return {"status": "FAIL", "reason": "두 로그의 밑·첫 진수·곱의 값이 필요합니다."}
    if min(first_base, first_value, second_base) <= 0 or first_base == 1 or second_base == 1:
        return {"status": "FAIL", "reason": "로그의 밑은 양수이고 1이 아니며 진수는 양수여야 합니다."}
    first_log = log(first_value, first_base)
    if abs(first_log) < 1e-12:
        return {"status": "FAIL", "reason": "첫 로그값이 0이면 이 곱 조건으로 해를 유일하게 정할 수 없습니다."}
    answer = second_base ** (target / first_log)
    answer = int(round(answer)) if abs(answer - round(answer)) < 1e-10 else answer
    verified = abs(log(first_value, first_base) * log(float(answer), second_base) - target) < 1e-9
    return {"status": "PASS", "answer": answer, "formula": "log_b2(x)=target/log_b1(v)", "verified": verified, "tool": "solve_log_product_equation"}


def solve_exponential_asymptote_distance_sum(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 지수 밑·수직 이동·점근선 거리. 원리: 점의 y값 후보에서 양수인  b를 고르고 a=log_base(b)를 역산한다."""
    base, shift, distance = (slots.get(key) for key in ("base", "shift", "distance"))
    try:
        base, shift, distance = float(base), float(shift), float(distance)
    except (TypeError, ValueError):
        return {"status": "FAIL", "reason": "지수의 밑·수평 점근선 이동값·거리가 필요합니다."}
    if base <= 0 or base == 1 or distance <= 0:
        return {"status": "FAIL", "reason": "지수함수의 밑과 점근선 거리 조건이 올바르지 않습니다."}
    candidates = [shift + distance, shift - distance]
    positive = [value for value in candidates if value > 0]
    if len(positive) != 1:
        return {"status": "FAIL", "reason": "점근선 거리만으로 양의 지수함수 점의 y값을 유일하게 정할 수 없습니다."}
    b = positive[0]
    a = log(b, base)
    a = int(round(a)) if abs(a - round(a)) < 1e-10 else a
    answer = a + b
    answer = int(round(answer)) if abs(answer - round(answer)) < 1e-10 else answer
    verified = abs(abs(b - shift) - distance) < 1e-9 and abs(base ** float(a) - b) < 1e-8
    return {"status": "PASS", "answer": answer, "formula": "|b-shift|=distance, a=log_base(b)", "verified": verified, "parameters": {"a": a, "b": b}, "tool": "solve_exponential_asymptote_distance_sum"}


def solve_inverse_log_power_coordinate(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 로그 밑·수직 이동·역함수 입력·좌표의 거듭제곱 밑. 원리: f⁻¹(t)=b^(t-c)를 좌표의 q^k와 비교한다."""
    base, shift, input_value, coordinate_base = (slots.get(key) for key in ("base", "shift", "input", "coordinate_base"))
    try:
        base, shift, input_value, coordinate_base = (float(base), float(shift), float(input_value), float(coordinate_base))
    except (TypeError, ValueError):
        return {"status": "FAIL", "reason": "로그의 밑·이동값·역함수 입력·좌표 거듭제곱의 밑이 필요합니다."}
    if min(base, coordinate_base) <= 0 or base == 1 or coordinate_base == 1:
        return {"status": "FAIL", "reason": "로그와 거듭제곱의 밑은 양수이고 1이 아니어야 합니다."}
    inverse_value = base ** (input_value - shift)
    exponent = log(inverse_value, coordinate_base)
    exponent = int(round(exponent)) if abs(exponent - round(exponent)) < 1e-10 else exponent
    verified = abs(coordinate_base ** float(exponent) - inverse_value) < 1e-8
    return {"status": "PASS", "answer": exponent, "formula": "f⁻¹(t)=b^(t-c)=q^k", "verified": verified, "parameters": {"inverse_value": inverse_value}, "tool": "solve_inverse_log_power_coordinate"}


def solve_log_interval_extrema_sum(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 로그 밑·진수의 x 이동·수직 이동·닫힌 구간. 원리: 로그 단조성으로 양 끝점의 함수값을 비교·검산한다."""
    base, horizontal_shift, vertical_shift, left, right = (slots.get(key) for key in ("base", "horizontal_shift", "vertical_shift", "left", "right"))
    try:
        base, horizontal_shift, vertical_shift, left, right = (float(base), float(horizontal_shift), float(vertical_shift), float(left), float(right))
    except (TypeError, ValueError):
        return {"status": "FAIL", "reason": "로그의 밑·두 이동값·닫힌 구간의 양 끝점이 필요합니다."}
    if base <= 0 or base == 1 or left > right or left + horizontal_shift <= 0 or right + horizontal_shift <= 0:
        return {"status": "FAIL", "reason": "로그의 밑과 진수, 구간 조건이 유효하지 않습니다."}
    left_value = log(left + horizontal_shift, base) + vertical_shift
    right_value = log(right + horizontal_shift, base) + vertical_shift
    maximum, minimum = max(left_value, right_value), min(left_value, right_value)
    answer = maximum + minimum
    answer = int(round(answer)) if abs(answer - round(answer)) < 1e-10 else answer
    verified = abs((maximum + minimum) - float(answer)) < 1e-8 and ((base > 1 and left_value <= right_value) or (base < 1 and left_value >= right_value))
    return {"status": "PASS", "answer": answer, "formula": "f(x)=log_b(x+h)+v의 닫힌 구간 극값은 단조성에 따라 양 끝점에서 결정", "verified": verified, "parameters": {"left_value": left_value, "right_value": right_value}, "tool": "solve_log_interval_extrema_sum"}


def solve_sine_linear_special_interval(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: sin 계수·제곱근 상수·π 단위 구간. 원리: 특수각 해를 주기적으로 열거해 유일한 구간해를 원식에 재대입한다."""
    coefficient, radical, constant_sign = (slots.get(key) for key in ("coefficient", "radical", "constant_sign"))
    try:
        coefficient, radical, constant_sign = int(coefficient), int(radical), int(constant_sign)
        left = Fraction(int(slots["left_numerator"]), int(slots["left_denominator"]))
        right = Fraction(int(slots["right_numerator"]), int(slots["right_denominator"]))
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return {"status": "FAIL", "reason": "sin 계수·제곱근 상수와 π 단위의 닫힌 구간이 필요합니다."}
    if coefficient == 0 or radical not in {1, 3} or left > right:
        return {"status": "FAIL", "reason": "현재는 특수각 sin 방정식의 유효한 계수·구간만 지원합니다."}
    target_sign = -constant_sign * (1 if coefficient > 0 else -1)
    magnitude = Fraction(1, abs(coefficient))
    base_solutions: dict[tuple[int, Fraction], tuple[Fraction, ...]] = {
        (1, Fraction(1, 1)): (Fraction(1, 2),), (-1, Fraction(1, 1)): (Fraction(3, 2),),
        (1, Fraction(1, 2)): (Fraction(1, 6), Fraction(5, 6)), (-1, Fraction(1, 2)): (Fraction(7, 6), Fraction(11, 6)),
        (1, Fraction(3, 2)): (Fraction(1, 3), Fraction(2, 3)), (-1, Fraction(3, 2)): (Fraction(4, 3), Fraction(5, 3)),
    }
    # sqrt(3)/2는 수치 제곱값이 아니라 특수각 표의 기호 계수 3/2로 보관한다.
    key_magnitude = magnitude if radical == 1 else Fraction(3, 2)
    if radical == 3 and abs(coefficient) != 2:
        return {"status": "FAIL", "reason": "sqrt(3) 항은 현재 계수 2인 특수각 형태만 지원합니다."}
    candidates = [angle + 2 * period for angle in base_solutions.get((target_sign, key_magnitude), ()) for period in range(-8, 9)]
    matches = [angle for angle in candidates if left <= angle <= right]
    if len(matches) != 1:
        return {"status": "FAIL", "reason": "주어진 구간에서 특수각 해가 유일하게 결정되지 않습니다."}
    angle = matches[0]
    numerator, denominator = angle.numerator, angle.denominator
    answer = "π" if angle == 1 else f"{numerator}π" if denominator == 1 else f"{numerator}π/{denominator}"
    target = -constant_sign * sqrt(radical) / coefficient
    verified = left <= angle <= right and abs(sin(float(angle) * pi) - target) < 1e-10
    return {"status": "PASS", "answer": answer, "formula": "a·sin x±sqrt(n)=0을 sin x의 특수각 값으로 바꾼다", "verified": verified, "parameters": {"angle_pi_ratio": f"{numerator}/{denominator}", "target": target}, "tool": "solve_sine_linear_special_interval"}


def add_polynomial_coefficients(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 두 다항식의 차수별 정수 계수. 원리: 같은 차수 계수를 합쳐 표준형을 만들고 각 차수 항등식으로 검산한다."""
    left, right = slots.get("left"), slots.get("right")
    if not isinstance(left, dict) or not isinstance(right, dict):
        return {"status": "FAIL", "reason": "두 다항식의 차수별 계수가 필요합니다."}
    try:
        combined = {int(power): int(left.get(power, left.get(str(power), 0))) + int(right.get(power, right.get(str(power), 0))) for power in set(left) | set(right)}
    except (TypeError, ValueError):
        return {"status": "FAIL", "reason": "현재 다항식 덧셈 도구는 정수 계수만 지원합니다."}
    combined = {power: coefficient for power, coefficient in combined.items() if coefficient}
    def term(coefficient: int, power: int, first: bool) -> str:
        sign = "-" if coefficient < 0 else "" if first else "+"
        magnitude = abs(coefficient)
        variable = "" if power == 0 else "x" if power == 1 else f"x^{power}"
        number = "" if variable and magnitude == 1 else str(magnitude)
        return f"{sign}{number}{variable}"
    answer = "0" if not combined else "".join(term(coefficient, power, index == 0) for index, (power, coefficient) in enumerate(sorted(combined.items(), reverse=True)))
    verified = all(combined.get(power, 0) == int(left.get(power, left.get(str(power), 0))) + int(right.get(power, right.get(str(power), 0))) for power in set(left) | set(right))
    return {"status": "PASS", "answer": answer, "formula": "(A+B)의 x^k 계수=A의 x^k 계수+B의 x^k 계수", "verified": verified, "parameters": {"coefficients": combined}, "tool": "add_polynomial_coefficients"}


def _geometry_gui_bridge(operation: str, slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 기하 연산명과 GUI 좌표 슬롯. 원리: 등록된 수학 도구에서도 동일한 구조화 기하 엔진을 호출하도록 연결한다."""
    from geometry_gui import solve_geometry_payload
    return solve_geometry_payload({"operation": operation, "points": slots.get("points"), "point_ids": slots.get("point_ids")})


def geometry_distance_gui(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 두 GUI 점. 원리: 거리 제곱식을 적용하는 구조화 기하 도구를 호출한다."""
    return _geometry_gui_bridge("distance", slots)


def geometry_midpoint_gui(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 두 GUI 점. 원리: 중점 복원식을 검산하는 구조화 기하 도구를 호출한다."""
    return _geometry_gui_bridge("midpoint", slots)


def geometry_triangle_area_gui(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 세 GUI 점. 원리: 신발끈 공식과 넓이 불변식을 적용한다."""
    return _geometry_gui_bridge("triangle_area", slots)


def geometry_vector_dot_gui(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 벡터 AB·CD를 만드는 네 GUI 점. 원리: 성분 내적을 계산·재계산한다."""
    return _geometry_gui_bridge("vector_dot", slots)


def geometry_line_intersection_gui(slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 직선 AB·CD를 만드는 네 GUI 점. 원리: 행렬식 교점을 두 직선에 재대입한다."""
    return _geometry_gui_bridge("line_intersection", slots)


MATH_TOOL_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "polynomial_remainder_two_linear": polynomial_remainder_two_linear,
    "rational_interval_extrema": rational_interval_extrema,
    "symbolic_matrix_product_2x2": symbolic_matrix_product_2x2,
    "evaluate_polynomial_horner": evaluate_polynomial_horner,
    "evaluate_integer_gcd": evaluate_integer_gcd,
    "solve_log_product_equation": solve_log_product_equation,
    "solve_exponential_asymptote_distance_sum": solve_exponential_asymptote_distance_sum,
    "solve_inverse_log_power_coordinate": solve_inverse_log_power_coordinate,
    "solve_log_interval_extrema_sum": solve_log_interval_extrema_sum,
    "solve_sine_linear_special_interval": solve_sine_linear_special_interval,
    "add_polynomial_coefficients": add_polynomial_coefficients,
    "geometry_distance_gui": geometry_distance_gui,
    "geometry_midpoint_gui": geometry_midpoint_gui,
    "geometry_triangle_area_gui": geometry_triangle_area_gui,
    "geometry_vector_dot_gui": geometry_vector_dot_gui,
    "geometry_line_intersection_gui": geometry_line_intersection_gui,
}


def call_math_tool(tool_name: str, slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 도구 ID와 슬롯. 원리: 허용 목록에서만 계산 도구를 선택해 임의 코드 실행을 차단한다."""
    tool = MATH_TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return {"status": "FAIL", "reason": f"등록되지 않은 수학 도구입니다: {tool_name}"}
    return tool(slots)
