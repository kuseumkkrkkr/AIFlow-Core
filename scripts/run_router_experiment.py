"""비공개 실제 수학 코퍼스에서 세 라우터의 비교 보고서를 생성한다."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from experiment_runner import evaluate_router, run_experiment, validate_private_records  # noqa: E402


def main() -> int:
    """변수: 비공개 코퍼스·출력 JSON·반복 횟수. 원리: 원문은 출력에 복제하지 않고 라우팅 평가 집계와 문항 해시만 UTF-8로 저장한다."""
    parser = argparse.ArgumentParser(description="AIFlow 세 라우터 비공개 코퍼스 비교")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--modes", nargs="+", choices=("rule", "neural", "embedding"),
                        help="실행할 라우터만 지정한다. 장기 임베딩 평가를 별도 실행할 때 사용한다.")
    args = parser.parse_args()
    if args.modes:
        records = json.loads(args.corpus.read_text(encoding="utf-8"))
        validate_private_records(records)
        report = {"source": str(args.corpus), "repeats": args.repeats,
                  "reports": [evaluate_router(records, mode, args.repeats) for mode in args.modes]}
    else:
        report = run_experiment(args.corpus, args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "routers": [item["router"] for item in report["reports"]]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
