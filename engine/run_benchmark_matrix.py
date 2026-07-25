"""여러 학년·seed·반복 횟수를 순회해 생성 검증 안정성을 측정한다."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from problem_generation_loop import GenerationConfig, generate_and_validate


def run_matrix(seeds: list[int], repeats: int) -> dict:
    """필요 변수: seed 목록·반복 횟수. 작동 원리: 교육과정 프로필별 독립 루프를 합산한다."""
    profiles = [("중3", "중3"), ("고1", "고1"), ("수1", "수1"), ("수2", "수2"), ("고2", "고2")]
    reports = []
    for seed in seeds:
        for min_grade, max_grade in profiles:
            reports.append(generate_and_validate(GenerationConfig(min_grade, max_grade, repeats, seed, True)))
    rows = [case for report in reports for case in report["cases"]]
    domain_total = Counter(row.get("domain") for row in rows)
    domain_passed = Counter(row.get("domain") for row in rows if row.get("status") == "PASS")
    return {
        "seeds": seeds,
        "repeats": repeats,
        "profile_count": len(profiles),
        "total": len(rows),
        "passed": sum(row.get("status") == "PASS" for row in rows),
        "failed": sum(row.get("status") != "PASS" for row in rows),
        "pass_rate": sum(row.get("status") == "PASS" for row in rows) / len(rows) if rows else 0.0,
        "domain_metrics": {
            domain: {"total": count, "passed": domain_passed[domain], "pass_rate": domain_passed[domain] / count}
            for domain, count in sorted(domain_total.items())
        },
        "reports": reports,
    }


def main() -> int:
    """명령행 인자를 읽어 매트릭스 결과를 UTF-8 JSON으로 저장한다."""
    parser = argparse.ArgumentParser(description="AIFlow-Core 다중 seed·학년 벤치마크")
    parser.add_argument("--seeds", default="11,22,33,44,55")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", default="docs/benchmark_matrix_report.json")
    args = parser.parse_args()
    seeds = [int(item.strip()) for item in args.seeds.split(",") if item.strip()]
    report = run_matrix(seeds, max(1, args.repeats))
    output = Path(args.output)
    if not output.is_absolute():
        output = Path(__file__).resolve().parents[1] / output
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SUMMARY passed={report['passed']} total={report['total']} rate={report['pass_rate']:.3f}")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
