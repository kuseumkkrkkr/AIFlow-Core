"""비공개 실제 수학 코퍼스에서 세 라우터의 비교 보고서를 생성한다."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from experiment_runner import run_experiment  # noqa: E402


def main() -> int:
    """변수: 비공개 코퍼스·출력 JSON·반복 횟수. 원리: 원문은 출력에 복제하지 않고 라우팅 평가 집계와 문항 해시만 UTF-8로 저장한다."""
    parser = argparse.ArgumentParser(description="AIFlow 세 라우터 비공개 코퍼스 비교")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    report = run_experiment(args.corpus, args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "routers": [item["router"] for item in report["reports"]]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
