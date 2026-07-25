"""생성 입력 범위 검증 회귀 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from problem_generation_loop import GenerationConfig, generate_and_validate  # noqa: E402


def test_reversed_grade_range_is_rejected() -> None:
    """최소 학년이 최대 학년보다 높으면 빈 PASS가 되지 않는지 확인한다."""
    try:
        generate_and_validate(GenerationConfig("고2", "중3"))
    except ValueError as exc:
        assert "앞서야" in str(exc)
    else:
        raise AssertionError("역전된 학년 범위가 거부되지 않았습니다.")


if __name__ == "__main__":
    test_reversed_grade_range_is_rejected()
    print("PASS: generation validation")
