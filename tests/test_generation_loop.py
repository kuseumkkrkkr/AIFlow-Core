"""생성 파라미터와 반복 검증 루프 회귀 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from problem_generation_loop import GenerationConfig, generate_and_validate  # noqa: E402


def test_generated_cases_pass() -> None:
    """고교 범위 독립 생성 문항이 전체 엔진과 기대 정답에 일치하는지 확인한다."""
    report = generate_and_validate(GenerationConfig(repeats=2, seed=77))
    assert report["total"] == 28
    assert report["failed"] == 0
    assert report["pass_rate"] == 1.0


if __name__ == "__main__":
    test_generated_cases_pass()
    print("PASS: generation loop")
