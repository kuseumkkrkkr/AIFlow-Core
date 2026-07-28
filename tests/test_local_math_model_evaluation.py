"""로컬 생성형 수학 모델 평가기의 답안 정규화 회귀를 확인한다."""
from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_local_math_model.py"
SPEC = importlib.util.spec_from_file_location("evaluate_local_math_model", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_answer_normalization_and_extraction() -> None:
    """변수: 표기 변형 응답. 원리: GSM8K 정답 비교에 필요한 숫자 정규화만 허용하는지 확인한다."""
    assert MODULE.normalize_answer("1,200") == "1200"
    assert MODULE.normalize_answer("6/4") == "1.5"
    assert MODULE.normalize_answer("$42.00") == "42"
    assert MODULE.extract_final_answer("계산 결과입니다.\nFINAL: 1,200") == "1200"
    assert MODULE.extract_final_answer("먼저 3을 더한다. 최종값은 42") == "42"
    assert MODULE.extract_final_answer("FINAL: 모름") is None


if __name__ == "__main__":
    test_answer_normalization_and_extraction()
    print("PASS: local model evaluator")
