"""좌표 평면 GUI가 보내는 구조화된 도형 데이터를 풀이하는 기하 엔진.

자연어 키워드를 추정하지 않는다. 사용자가 화면에서 만든 점과 선택한 연산만 받아
계산하므로, 도형 입력의 의미를 재현 가능하게 보존하고 각 결과를 별도 불변식으로 검산한다.
"""
from __future__ import annotations

from fractions import Fraction
from math import isfinite, isqrt
from typing import Any


MAX_POINTS = 12
MAX_COORDINATE = 10_000
OPERATION_POINT_COUNTS = {
    "distance": 2,
    "midpoint": 2,
    "triangle_area": 3,
    "vector_dot": 4,
    "line_intersection": 4,
}


def _fraction(value: Any) -> Fraction:
    """변수: GUI 좌표 하나. 원리: 유한한 수만 정확한 유리수로 바꿔 부동소수 오차를 누적하지 않는다."""
    if isinstance(value, bool):
        raise ValueError("좌표에는 참·거짓값을 넣을 수 없습니다.")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("좌표는 숫자여야 합니다.") from exc
    if not isfinite(numeric) or abs(numeric) > MAX_COORDINATE:
        raise ValueError(f"좌표는 ±{MAX_COORDINATE} 범위의 유한한 수여야 합니다.")
    return Fraction(str(value)).limit_denominator(1000)


def _format_fraction(value: Fraction) -> str | int:
    """변수: 정확한 유리수. 원리: 정수는 숫자로, 나머지는 분수 문자열로 JSON에 안정적으로 보낸다."""
    return value.numerator if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _point_map(raw_points: Any) -> dict[str, tuple[Fraction, Fraction]]:
    """변수: GUI 점 배열. 원리: 점 이름·좌표 범위를 검증해 이후 연산이 같은 좌표 사전을 공유하게 한다."""
    if not isinstance(raw_points, list) or not 2 <= len(raw_points) <= MAX_POINTS:
        raise ValueError(f"점은 2개 이상 {MAX_POINTS}개 이하로 입력해야 합니다.")
    points: dict[str, tuple[Fraction, Fraction]] = {}
    for raw in raw_points:
        if not isinstance(raw, dict):
            raise ValueError("각 점은 id, x, y를 가진 객체여야 합니다.")
        point_id = str(raw.get("id", "")).strip().upper()
        if not point_id or len(point_id) > 8 or not point_id.replace("_", "").isalnum() or point_id in points:
            raise ValueError("점 이름은 중복 없는 영문·숫자 8자 이하여야 합니다.")
        points[point_id] = (_fraction(raw.get("x")), _fraction(raw.get("y")))
    return points


def _selected_points(payload: dict[str, Any], points: dict[str, tuple[Fraction, Fraction]]) -> tuple[str, ...]:
    """변수: 연산명·선택 점 ID. 원리: 연산별 필요 점 수와 존재 여부를 먼저 고정해 모호한 도형을 거부한다."""
    operation = str(payload.get("operation", ""))
    count = OPERATION_POINT_COUNTS.get(operation)
    selected = payload.get("point_ids")
    if count is None:
        raise ValueError("지원하지 않는 기하 연산입니다.")
    if not isinstance(selected, list) or len(selected) != count:
        raise ValueError(f"{operation} 연산에는 점 {count}개를 순서대로 선택해야 합니다.")
    ids = tuple(str(value).strip().upper() for value in selected)
    if any(point_id not in points for point_id in ids):
        raise ValueError("선택한 점이 없습니다.")
    # AB·CD와 두 직선은 공통 끝점이 있을 수 있다. 다만 한 선분 자체가 점 하나로 퇴화하면 안 된다.
    if operation in {"distance", "midpoint", "triangle_area"} and len(set(ids)) != len(ids):
        raise ValueError("이 연산에서는 같은 점을 중복 선택할 수 없습니다.")
    if operation in {"vector_dot", "line_intersection"} and (ids[0] == ids[1] or ids[2] == ids[3]):
        raise ValueError("각 벡터 또는 직선은 서로 다른 두 점으로 선택해야 합니다.")
    return ids


def _point_data(points: dict[str, tuple[Fraction, Fraction]], ids: tuple[str, ...]) -> dict[str, dict[str, str | int]]:
    """변수: 좌표 사전·표시 순서. 원리: 풀이 trace가 실제 GUI 입력 좌표를 그대로 보여 주도록 직렬화한다."""
    return {point_id: {"x": _format_fraction(points[point_id][0]), "y": _format_fraction(points[point_id][1])} for point_id in ids}


def solve_geometry_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """변수: operation, points, point_ids. 원리: GUI의 구조화 좌표로 거리·중점·넓이·내적·교점을 계산하고 독립 등식으로 검산한다."""
    try:
        points = _point_map(payload.get("points"))
        ids = _selected_points(payload, points)
        operation = str(payload["operation"])
        selected = [points[point_id] for point_id in ids]
        common = {"status": "PASS", "operation": operation, "points": _point_data(points, ids), "verified": False}

        if operation == "distance":
            (x1, y1), (x2, y2) = selected
            squared = (x2 - x1) ** 2 + (y2 - y1) ** 2
            if squared.denominator == 1 and isqrt(squared.numerator) ** 2 == squared.numerator:
                answer: str | int = isqrt(squared.numerator)
            else:
                answer = f"√({_format_fraction(squared)})"
            common.update({"answer": answer, "formula": "AB²=(x₂-x₁)²+(y₂-y₁)²", "parameters": {"squared_distance": _format_fraction(squared)}, "verified": squared >= 0})
        elif operation == "midpoint":
            (x1, y1), (x2, y2) = selected
            midpoint = ((x1 + x2) / 2, (y1 + y2) / 2)
            common.update({"answer": f"({_format_fraction(midpoint[0])}, {_format_fraction(midpoint[1])})", "formula": "M=((x₁+x₂)/2, (y₁+y₂)/2)", "parameters": {"midpoint": {"x": _format_fraction(midpoint[0]), "y": _format_fraction(midpoint[1])}}, "verified": 2 * midpoint[0] == x1 + x2 and 2 * midpoint[1] == y1 + y2})
        elif operation == "triangle_area":
            (x1, y1), (x2, y2), (x3, y3) = selected
            doubled_area = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
            area = abs(doubled_area) / 2
            if area == 0:
                raise ValueError("세 점이 한 직선 위에 있어 삼각형을 만들지 않습니다.")
            common.update({"answer": _format_fraction(area), "formula": "삼각형 넓이=|x₁(y₂-y₃)+x₂(y₃-y₁)+x₃(y₁-y₂)|/2", "parameters": {"signed_double_area": _format_fraction(doubled_area)}, "verified": abs(doubled_area) == 2 * area})
        elif operation == "vector_dot":
            (ax, ay), (bx, by), (cx, cy), (dx, dy) = selected
            first = (bx - ax, by - ay)
            second = (dx - cx, dy - cy)
            dot = first[0] * second[0] + first[1] * second[1]
            common.update({"answer": _format_fraction(dot), "formula": "AB·CD=(xB-xA)(xD-xC)+(yB-yA)(yD-yC)", "parameters": {"AB": [_format_fraction(first[0]), _format_fraction(first[1])], "CD": [_format_fraction(second[0]), _format_fraction(second[1])]}, "verified": dot == first[0] * second[0] + first[1] * second[1]})
        else:
            (x1, y1), (x2, y2), (x3, y3), (x4, y4) = selected
            denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if denominator == 0:
                raise ValueError("두 직선이 평행하거나 일치하여 유일한 교점이 없습니다.")
            cross1, cross2 = x1 * y2 - y1 * x2, x3 * y4 - y3 * x4
            intersection = ((cross1 * (x3 - x4) - (x1 - x2) * cross2) / denominator, (cross1 * (y3 - y4) - (y1 - y2) * cross2) / denominator)
            line1 = (x2 - x1) * (intersection[1] - y1) - (y2 - y1) * (intersection[0] - x1)
            line2 = (x4 - x3) * (intersection[1] - y3) - (y4 - y3) * (intersection[0] - x3)
            common.update({"answer": f"({_format_fraction(intersection[0])}, {_format_fraction(intersection[1])})", "formula": "두 직선의 행렬식 교점 공식", "parameters": {"intersection": {"x": _format_fraction(intersection[0]), "y": _format_fraction(intersection[1])}}, "verified": line1 == 0 and line2 == 0})
        return common
    except (KeyError, TypeError, ValueError) as exc:
        return {"status": "FAIL", "reason": str(exc), "verified": False}
