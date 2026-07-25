"""교육과정 태그를 가진 문제를 생성하고 전체 엔진으로 반복 검증한다."""
from __future__ import annotations

import json
import random
import argparse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rule_based_nlp import build_solution_trace, classify, select_optimal_rule, solve_rule


@dataclass(frozen=True)
class GenerationConfig:
    """필요 변수: 학년 범위·반복 횟수·seed. 작동 원리: 생성 실험을 재현 가능하게 고정한다."""

    min_grade: str = "중3"
    max_grade: str = "고2"
    repeats: int = 3
    seed: int = 2026
    include_mock: bool = True
    difficulty: str = "mixed"


@dataclass(frozen=True)
class GeneratedCase:
    """필요 변수: 문항·정답·교육과정 태그. 작동 원리: 생성 기대값과 엔진 결과를 비교한다."""

    case_id: str
    curriculum: str
    mock_style: str
    question: str
    expected: Any
    difficulty: str = "mixed"


def _cases(rng: random.Random, include_mock: bool) -> list[GeneratedCase]:
    """필요 변수: 난수 생성기·모의고사 여부. 작동 원리: 독립 계산으로 기대 정답을 만든다."""
    a, d, n = rng.randint(-5, 12), rng.randint(-5, 8), rng.randint(3, 18)
    p, q = rng.randint(2, 8), rng.randint(1, 7)
    cases = [
        GeneratedCase("m3-linear", "중3", "중3 모의고사", f"{p}x+{q}={p * 6 + q}에서 x의 값", 6),
        GeneratedCase("m3-set", "중3", "중3 모의고사", "|A|=18, |B|=12, |A∩B|=5일 때 |A∪B|", 25),
        GeneratedCase("m3-geometry", "중3", "중3 모의고사", "피타고라스 직각삼각형의 두 변 9, 12일 때 빗변", 15),
        GeneratedCase("h1-seq", "고1", "고1 내신형", f"등차수열 첫항 {a}, 공차 {d}일 때 a{n}", a + (n - 1) * d),
        GeneratedCase("h1-function", "고1", "고1 내신형", "함수 f(x)=3x-4, x=7일 때 함숫값", 17),
        GeneratedCase("h1-composition", "고1", "고1 내신형", "합성함수 f(x)=2x+1, g(x)=3x+2에서 f(g(4))", 29),
        GeneratedCase("h1-inverse", "고1", "고1 내신형", "f(x)=4x-7의 역함수", "(x+7)/4"),
        GeneratedCase("h1-factor", "고1", "고1 내신형", "인수분해 x²-9x+20", "(x-5)(x-4)"),
        GeneratedCase("s1-quadratic", "수1", "고2 모의고사", "이차방정식 1x²-13x+36=0의 정수근", 9),
        GeneratedCase("s1-probability", "수1", "고2 모의고사", "확률 3/8", 0.375),
        GeneratedCase("s1-combination", "수1", "고2 모의고사", "10개 중 3개를 뽑는 조합의 수", 120),
        GeneratedCase("s2-seq-sum", "수2", "고2 모의고사", "등차수열 첫항 5, 공차 2의 첫 6항의 합", 60),
        GeneratedCase("s2-conditional", "수2", "고2 모의고사", "조건부확률 P(A∩B)=1/10, P(B)=1/2일 때 P(A|B)", 0.2),
        GeneratedCase("s1-exp", "수1", "고2 모의고사", "지수 2^8", 256),
        GeneratedCase("s1-log", "수1", "고2 모의고사", "log_3 27", 3),
        GeneratedCase("s1-trig", "수1", "고2 모의고사", "삼각함수 cos 60", 0.5),
        GeneratedCase("s2-limit", "수2", "고2 모의고사", "극한 lim x->3 x²+3x", 18),
        GeneratedCase("s2-derivative", "수2", "고2 모의고사", "미분 f(x)=x^4, x=2", 32),
        GeneratedCase("s2-integral", "수2", "고2 모의고사", "정적분 0부터 3 x^2", 9),
    ]
    if include_mock:
        cases.append(GeneratedCase("mock-mixed", "고2", "고2 모의고사", "원의 넓이 반지름 3", 28.274333882308138))
    return cases


def generate_and_validate(config: GenerationConfig) -> dict[str, Any]:
    """필요 변수: GenerationConfig. 작동 원리: 반복 생성 후 분류·계산·검산·trace를 모두 기록한다."""
    rng = random.Random(config.seed)
    rows: list[dict[str, Any]] = []
    for repeat in range(max(1, config.repeats)):
        grade_order = ["중3", "고1", "수1", "수2", "고2"]
        profile_groups = {
            "중3": {"중3"},
            "고1": {"고1"},
            "수1": {"수1"},
            "수2": {"수2"},
            # 고2 모의고사는 수1·수2 누적 범위를 포함한다.
            "고2": {"수1", "수2", "고2"},
        }
        if config.min_grade in profile_groups and config.max_grade in profile_groups:
            start = grade_order.index(config.min_grade)
            end = grade_order.index(config.max_grade)
            allowed = set().union(*(profile_groups[grade] for grade in grade_order[start : end + 1]))
        else:
            allowed = set().union(*profile_groups.values())
        for case in _cases(rng, config.include_mock):
            case_difficulty = "basic" if case.case_id.startswith(("m3", "h1")) else "hard"
            if config.difficulty not in {"mixed", case_difficulty}:
                continue
            if case.curriculum not in allowed:
                continue
            parsed = classify(case.question)
            result = solve_rule(parsed["domain"], parsed["slots"])
            path = select_optimal_rule(parsed)
            answer_ok = result.get("answer") == case.expected or (
                isinstance(result.get("answer"), (int, float))
                and abs(float(result["answer"]) - float(case.expected)) < 1e-9
            )
            passed = result.get("status") == "PASS" and answer_ok and result.get("verified") is True
            rows.append({
                "repeat": repeat + 1,
                **asdict(case),
                "difficulty": case_difficulty,
                "domain": parsed.get("domain"),
                "rule_path": path.get("path", []),
                "answer": result.get("answer"),
                "formula": result.get("formula", ""),
                "reason": result.get("reason", ""),
                "trace": build_solution_trace(parsed, result) if result.get("status") == "PASS" else [],
                "verified": result.get("verified", False),
                "trace_steps": len(build_solution_trace(parsed, result)) if result.get("status") == "PASS" else 0,
                "status": "PASS" if passed else "FAIL",
            })
    passed = sum(row["status"] == "PASS" for row in rows)
    return {"config": asdict(config), "total": len(rows), "passed": passed, "failed": len(rows) - passed, "pass_rate": passed / len(rows) if rows else 0.0, "cases": rows}


def main() -> int:
    """명령행에서 고교 범위 반복 검증 보고서를 UTF-8 JSON으로 저장한다."""
    parser = argparse.ArgumentParser(description="AIFlow-Core 문제 생성·정답·풀이 검증 루프")
    parser.add_argument("--min-grade", default="중3", choices=["중3", "고1", "수1", "수2", "고2"])
    parser.add_argument("--max-grade", default="고2", choices=["중3", "고1", "수1", "수2", "고2"])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--no-mock", action="store_true", help="모의고사 스타일 문항 제외")
    parser.add_argument("--difficulty", choices=["basic", "mixed", "hard"], default="mixed")
    parser.add_argument("--output", default="docs/generated_validation_report.json")
    args = parser.parse_args()
    report = generate_and_validate(GenerationConfig(args.min_grade, args.max_grade, max(1, args.repeats), args.seed, not args.no_mock, args.difficulty))
    output = Path(args.output)
    if not output.is_absolute():
        output = Path(__file__).resolve().parents[1] / output
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SUMMARY passed={report['passed']} total={report['total']} rate={report['pass_rate']:.3f}")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
