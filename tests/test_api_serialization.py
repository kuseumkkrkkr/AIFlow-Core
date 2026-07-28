"""수학 객체가 웹 API 응답에서 UTF-8 JSON으로 유지되는지 검증한다."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "engine"))

from rule_based_nlp import classify, solve_rule  # noqa: E402
from algorithm import ALGORITHM  # noqa: E402
from solve import _json_default  # noqa: E402


def test_binomial_fraction_slot_is_json_safe() -> None:
    """이항분포의 정확한 Fraction 슬롯이 API 전송 중 오류를 내지 않는지 확인한다."""
    parsed = classify("이항분포 n=5, p=1/2에서 X=2일 확률")
    result = solve_rule(parsed["domain"], parsed["slots"])
    encoded = json.dumps({"parse": parsed, "result": result}, ensure_ascii=False, default=_json_default)
    assert '"p": "1/2"' in encoded
    assert result["answer"] == 0.3125


def test_algorithm_exposes_private_experiment_report_contract() -> None:
    """실전 원문을 공개하지 않아도 API가 세 라우터의 지표·반복 계약을 식별 가능하게 제공하는지 확인한다."""
    report_contract = ALGORITHM["routing_experiments"]["private_report_contract"]
    assert report_contract["repeats"] == 2
    assert "deterministic_pass_rate" in report_contract["metrics"]


if __name__ == "__main__":
    test_binomial_fraction_slot_is_json_safe()
    test_algorithm_exposes_private_experiment_report_contract()
    print("PASS: API serialization")
