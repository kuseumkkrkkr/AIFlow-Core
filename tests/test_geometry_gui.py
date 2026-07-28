"""좌표 평면 GUI 기하 엔진의 계산·거부 경계를 검증한다."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from geometry_gui import solve_geometry_payload  # noqa: E402


POINTS = [
    {"id": "A", "x": 0, "y": 0}, {"id": "B", "x": 4, "y": 0},
    {"id": "C", "x": 0, "y": 3}, {"id": "D", "x": 4, "y": 3},
]


def test_gui_geometry_operations_are_verified() -> None:
    """변수: 직각삼각형 좌표. 원리: 각 GUI 연산이 정확한 정답과 독립 검산 PASS를 함께 반환해야 한다."""
    cases = [
        ("distance", ["A", "B"], 4), ("midpoint", ["A", "D"], "(2, 3/2)"),
        ("triangle_area", ["A", "B", "C"], 6), ("vector_dot", ["A", "B", "A", "C"], 0),
        ("line_intersection", ["A", "D", "B", "C"], "(2, 3/2)"),
    ]
    for operation, point_ids, answer in cases:
        result = solve_geometry_payload({"operation": operation, "points": POINTS, "point_ids": point_ids})
        assert result["status"] == "PASS"
        assert result["answer"] == answer
        assert result["verified"] is True


def test_gui_geometry_rejects_degenerate_or_unknown_points() -> None:
    """변수: 퇴화 삼각형·없는 점. 원리: 불충분한 기하 입력은 정답 대신 FAIL이어야 한다."""
    collinear = [{"id": "A", "x": 0, "y": 0}, {"id": "B", "x": 1, "y": 1}, {"id": "C", "x": 2, "y": 2}]
    assert solve_geometry_payload({"operation": "triangle_area", "points": collinear, "point_ids": ["A", "B", "C"]})["status"] == "FAIL"
    assert solve_geometry_payload({"operation": "distance", "points": POINTS, "point_ids": ["A", "Z"]})["status"] == "FAIL"


if __name__ == "__main__":
    test_gui_geometry_operations_are_verified()
    test_gui_geometry_rejects_degenerate_or_unknown_points()
    print("PASS: geometry GUI")
