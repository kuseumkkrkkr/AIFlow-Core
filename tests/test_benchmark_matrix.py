"""다중 학년·seed 벤치마크 회귀 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from run_benchmark_matrix import run_matrix  # noqa: E402


def test_matrix_is_stable() -> None:
    """두 seed와 다섯 교육과정 프로필을 모두 통과하는지 확인한다."""
    report = run_matrix([7, 13], 1)
    assert report["total"] == 62
    assert report["failed"] == 0
    assert report["pass_rate"] == 1.0


if __name__ == "__main__":
    test_matrix_is_stable()
    print("PASS: benchmark matrix")
