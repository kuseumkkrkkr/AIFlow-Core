"""외부 문제 코퍼스 검증기 회귀 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from corpus_runner import run_corpus  # noqa: E402


def test_sample_corpus() -> None:
    """샘플 모의고사형 코퍼스가 모두 통과하는지 확인한다."""
    report = run_corpus(Path(__file__).resolve().parents[1] / "benchmarks" / "market_style_corpus.json")
    assert report["total"] == 20
    assert report["failed"] == 0


if __name__ == "__main__":
    test_sample_corpus()
    print("PASS: corpus runner")
