"""AIFlow-Core가 규칙에서 호출하는 재사용 가능한 수학 계산 도구 모음.

각 도구는 이미 추출된 슬롯만 받아 계산한다. 자연어 해석과 수학 계산을 분리해,
특정 시험 문항의 숫자나 정답을 코드에 고정하지 않는다.
"""
from __future__ import annotations

from typing import Any, Callable


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


MATH_TOOL_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "polynomial_remainder_two_linear": polynomial_remainder_two_linear,
    "rational_interval_extrema": rational_interval_extrema,
    "symbolic_matrix_product_2x2": symbolic_matrix_product_2x2,
}


def call_math_tool(tool_name: str, slots: dict[str, Any]) -> dict[str, Any]:
    """변수: 도구 ID와 슬롯. 원리: 허용 목록에서만 계산 도구를 선택해 임의 코드 실행을 차단한다."""
    tool = MATH_TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return {"status": "FAIL", "reason": f"등록되지 않은 수학 도구입니다: {tool_name}"}
    return tool(slots)
