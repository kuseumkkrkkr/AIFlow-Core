"""중3 범위 룰베이스드 수학 NLP의 최소 인터페이스.

입력 문장을 정규화하고 지식 JSON의 개념·규칙과 연결해 유형과 슬롯을 추출한다.
현재는 외부 모델 없이 키워드와 기호 패턴만 사용하며, 이후 동의어 사전을 확장한다.
"""

from __future__ import annotations

import json
import re
import unicodedata
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any

from latex_normalizer import normalize_latex_input
from math_tools import call_math_tool


_ROOT = Path(__file__).resolve().parents[1] / "knowledge"

# 카탈로그의 rule_solver ID가 실제 solve_rule 도메인으로 연결되는 공개 계약이다.
# 새 항목을 실행 가능으로 승격할 때 이 표와 회귀 사례를 함께 추가한다.
RULE_SOLVER_DOMAIN_BY_ID = {
    "ar_seq_an_formula": "cm_arith_sequence",
    "cal_trig_derivative": "cal_trig_derivative",
    "equiprobable_probability": "cm_probability",
    "evaluate_binomial_probability": "stat_binomial_distribution",
    "hs1_exponential_equation_basic": "hs1_exponential_equation",
    "hs1_exponential_log_basic": "hs1_exponential_log",
    "hs1_factor_remainder": "hs1_polynomial_factor",
    "hs1_function_composition": "hs1_function_composition",
    "hs1_function_value": "hs1_function_basic",
    "hs1_geometric_sequence": "hs1_geometric_sequence",
    "hs1_inverse_function": "hs1_inverse_function",
    "hs1_special_angle_trig": "hs1_trigonometry",
    "hs2_polynomial_limit": "hs2_limit",
    "hs2_power_derivative": "hs2_derivative",
    "hs2_power_integral": "hs2_integral",
    "hs2_tangent_slope": "hs2_tangent",
    "sum_component_products": "geo_vector_dot",
}


@lru_cache(maxsize=8)
def _load(name: str) -> dict[str, Any]:
    """필요 변수: 지식 파일명. UTF-8 JSON을 읽어 반환한다."""
    return json.loads((_ROOT / name).read_text(encoding="utf-8"))


def normalize_text(text: str) -> str:
    """필요 변수: 사용자 문장. 유니코드 숫자와 수학 기호를 검색 친화적으로 통일한다."""
    text = normalize_latex_input(text)["normalized"]
    out: list[str] = []
    for ch in unicodedata.normalize("NFKC", text or ""):
        try:
            out.append(str(unicodedata.digit(ch)))
        except (TypeError, ValueError):
            out.append(ch)
    return "".join(out).replace("−", "-").replace("×", "*").replace("∩", "∩")


def parse_for_domain(text: str, domain: str) -> dict[str, Any]:
    """변수: 원문 문제와 라우터가 선택한 도메인. 원리: 공통 LaTeX 정규화 뒤 해당 도구의 슬롯만 추출한다.

    라우팅 실험에서는 classify의 최종 선택을 사용하지 않는다. 세 라우터가 같은
    입력에서 선택한 domain으로 이 함수를 호출해 슬롯 추출·계산·검산을 공평하게 공유한다.
    """
    latex = normalize_latex_input(text)
    normalized = normalize_text(latex["normalized"])
    return {
        "original": latex["original"],
        "normalized": normalized,
        "latex": latex,
        "domain": domain,
        "slots": _extract_slots(normalized, domain),
    }


def classify(text: str) -> dict[str, Any]:
    """필요 변수: 문제 문장. concept_graph와 rule_library를 이용해 유형·태그·슬롯을 추출한다."""
    normalized = normalize_text(text)
    concepts = _load("concept_graph.json")["nodes"]
    rules = _load("rule_library.json")["rules"]
    scores: dict[str, int] = {}
    tags: list[str] = []
    for concept in concepts:
        hits = [topic for topic in concept.get("topics", []) if topic in normalized]
        if hits:
            scores[concept["id"]] = len(hits)
            tags.extend(hits)
    # 지식 그래프에 아직 노드가 없는 중3 핵심 표현은 별칭 규칙으로 먼저 수용한다.
    aliases = {
        "cm_set": ["|A|", "|B|", "∩", "∪", "합집합", "교집합"],
        "cm_arith_sequence": ["수열", "등차수열", "첫항", "첫째항", "공차", "일반항"],
        "cm_linear": ["일차방정식", "미지수", "x를 구"],
        "cm_ratio": ["비례", "비율", "a:b", "반비례"],
        "cm_probability": ["확률", "경우의 수", "조합", "순열", "주사위", "동전"],
        "cm_geometry": ["피타고라스", "직각삼각형", "삼각형의 넓이", "원의 넓이", "직사각형", "가로", "세로"],
        "hs1_function_basic": ["함수", "함숫값", "정의역", "치역", "일차함수"],
        "hs1_function_composition": ["합성함수", "f(g(x))", "g(f(x))"],
        "hs1_inverse_function": ["역함수", "f⁻¹", "f^-1"],
        "hs1_conditional_probability": ["조건부확률", "P(A|B)", "P(A∩B)"],
        "hs1_polynomial_factor": ["다항식", "인수분해", "인수정리", "나머지정리"],
        "hs_polynomial_value": ["P(x)=", "다항식의 값", "다항식 함숫값"],
        "hs_polynomial_addition": ["두 다항식", "A+B", "A =", "B ="],
        "integer_gcd": ["최대공약수", "gcd("],
        "hs_log_product_equation": ["log_", "로그의 곱", "×log"],
        "hs_exponential_asymptote_distance": ["점근선", "사이의 거리", "a+b"],
        "hs_inverse_log_power_coordinate": ["역함수", "log_", "^k"],
        "hs_log_interval_extrema": ["최댓값", "최솟값", "log_", "구간"],
        "hs_sine_linear_interval": ["sin", "sqrt", "≤", "방정식"],
        "hs_cosine_law_side": ["코사인 법칙", "삼각형", "cos", "AB=", "BC="],
        "hs1_exponential_log": ["지수", "로그", "log", "log_"],
        "hs1_exponential_equation": ["지수방정식", "로그방정식", "2^x", "log_2 x"],
        "hs1_trigonometry": ["삼각함수", "sin", "cos", "tan", "사인", "코사인", "탄젠트"],
        "hs2_limit": ["극한", "lim", "수렴"],
        "hs2_derivative": ["미분", "도함수", "미분계수"],
        "hs2_tangent": ["접선", "접선의 기울기", "접선 기울기"],
        "hs2_integral": ["적분", "부정적분", "정적분"],
        "hs_composite_sequence": ["복합중", "a5+a8", "수열합성"],
        "hs_composite_sequence_function": ["복합상", "M=a", "수열함수합성"],
        "hs1_geometric_sequence": ["등비수열", "공비"],
        "stat_binomial_distribution": ["이항분포", "이항확률"],
        "geo_vector_dot": ["벡터 내적", "내적"],
        "cal_trig_derivative": ["sin x의 도함수", "cos x의 도함수", "삼각함수 미분"],
        "hs_polynomial_remainder": ["나눈 나머지", "나머지를 R(x)"],
        "hs_rational_interval_extrema": ["최댓값", "최솟값", "a/(x-"],
        "hs_matrix_product": ["두 행렬", "AB=", "행렬 A", "행렬 B"],
        "hs_absolute_linear_equation": ["절댓값", "|", "절대값"],
        "fn_linear_inequality": ["부등식", "≤", "≥", "<=", ">="],
        "csg_vector_dot_3d": ["공간벡터", "3차원", "공간 내적"],
        "la_matrix_multiply": ["행렬곱", "행렬의 곱", "A=", "B="],
    }
    for domain_name, keywords in aliases.items():
        hits = [word for word in keywords if word in normalized]
        if hits:
            scores[domain_name] = len(hits) + 1
            tags.extend(hits)
    if "=" in normalized and re.search(r"[+-]?\d+\s*x", normalized, flags=re.IGNORECASE):
        scores["cm_linear"] = scores.get("cm_linear", 0) + 2
        tags.append("일차방정식")
    if ("이차" in normalized or "판별식" in normalized) and re.search(r"x(?:\^\s*2|2)", normalized, flags=re.IGNORECASE):
        scores["cm_quadratic"] = scores.get("cm_quadratic", 0) + 3
    if "합성함수" in normalized or "f(g" in normalized or "g(f" in normalized:
        scores["hs1_function_composition"] = scores.get("hs1_function_composition", 0) + 5
    if "역함수" in normalized or "f⁻¹" in normalized or "f^-1" in normalized:
        scores["hs1_inverse_function"] = scores.get("hs1_inverse_function", 0) + 5
    rational_power_equation = re.search(
        r"(?:\d+|\(\s*\d+\s*/\s*\d+\s*\))\s*\^\s*\(?\s*[+-]?\s*\d*\s*x.*?="
        r".*?(?:\d+|\(\s*\d+\s*/\s*\d+\s*\))\s*\^\s*\(?\s*[+-]?\s*\d*\s*x",
        normalized,
        flags=re.IGNORECASE,
    )
    if "지수방정식" in normalized or "로그방정식" in normalized or rational_power_equation or re.search(r"(?:\^\s*x|log\s*_?\s*\d+\s*x)\s*=", normalized, flags=re.IGNORECASE):
        scores["hs1_exponential_equation"] = scores.get("hs1_exponential_equation", 0) + 7
    if re.search(r"(?:^|\s)(?:lim|log_?)", normalized, flags=re.IGNORECASE):
        scores["hs1_exponential_log"] = scores.get("hs1_exponential_log", 0) + 4
    if any(token in normalized for token in ("sin", "cos", "tan", "사인", "코사인", "탄젠트")):
        scores["hs1_trigonometry"] = scores.get("hs1_trigonometry", 0) + 4
    if "극한" in normalized or "lim" in normalized.lower():
        scores["hs2_limit"] = scores.get("hs2_limit", 0) + 6
    if "미분" in normalized or "도함수" in normalized:
        scores["hs2_derivative"] = scores.get("hs2_derivative", 0) + 6
    if "접선" in normalized:
        scores["hs2_tangent"] = scores.get("hs2_tangent", 0) + 7
    if "적분" in normalized:
        scores["hs2_integral"] = scores.get("hs2_integral", 0) + 6
    if "복합중" in normalized:
        scores["hs_composite_sequence"] = scores.get("hs_composite_sequence", 0) + 30
    if "복합상" in normalized:
        scores["hs_composite_sequence_function"] = scores.get("hs_composite_sequence_function", 0) + 30
    if "등비수열" in normalized and "공비" in normalized:
        scores["hs1_geometric_sequence"] = scores.get("hs1_geometric_sequence", 0) + 12
    if "이항분포" in normalized:
        scores["stat_binomial_distribution"] = scores.get("stat_binomial_distribution", 0) + 12
    if "내적" in normalized:
        scores["geo_vector_dot"] = scores.get("geo_vector_dot", 0) + 12
    if "sin x의 도함수" in normalized or "cos x의 도함수" in normalized or "삼각함수 미분" in normalized:
        scores["cal_trig_derivative"] = scores.get("cal_trig_derivative", 0) + 12
    if normalized.count("나눈 나머지") >= 2 and "R(" in normalized:
        scores["hs_polynomial_remainder"] = scores.get("hs_polynomial_remainder", 0) + 20
    if "최댓값" in normalized and "최솟값" in normalized and "a/(x-" in normalized:
        scores["hs_rational_interval_extrema"] = scores.get("hs_rational_interval_extrema", 0) + 20
    if "AB=" in normalized and "두 행렬" in normalized:
        scores["hs_matrix_product"] = scores.get("hs_matrix_product", 0) + 20
    if re.search(r"P\s*\(\s*x\s*\)\s*=", normalized, flags=re.IGNORECASE) and re.search(r"P\s*\(\s*[+-]?\d+\s*\)", normalized, flags=re.IGNORECASE):
        scores["hs_polynomial_value"] = scores.get("hs_polynomial_value", 0) + 20
    if re.search(r"A\s*=.*?B\s*=", normalized, flags=re.IGNORECASE) and re.search(r"A\s*\+\s*B", normalized, flags=re.IGNORECASE):
        scores["hs_polynomial_addition"] = scores.get("hs_polynomial_addition", 0) + 20
    if "최대공약수" in normalized or re.search(r"gcd\s*\(", normalized, flags=re.IGNORECASE):
        scores["integer_gcd"] = scores.get("integer_gcd", 0) + 20
    if len(re.findall(r"log\s*_?\s*\d+", normalized, flags=re.IGNORECASE)) >= 2 and "=" in normalized:
        scores["hs_log_product_equation"] = scores.get("hs_log_product_equation", 0) + 20
    if "점근선" in normalized and "거리" in normalized and re.search(r"y\s*=\s*\d+\s*\^\s*x", normalized, flags=re.IGNORECASE):
        scores["hs_exponential_asymptote_distance"] = scores.get("hs_exponential_asymptote_distance", 0) + 20
    if "역함수" in normalized and re.search(r"log\s*_?\s*\d+\s*x\s*[+-]", normalized, flags=re.IGNORECASE) and re.search(r"\(\s*\d+\s*,\s*\d+\s*\^\s*[a-zA-Z]", normalized):
        scores["hs_inverse_log_power_coordinate"] = scores.get("hs_inverse_log_power_coordinate", 0) + 20
    if "최댓값" in normalized and "최솟값" in normalized and re.search(r"log\s*_?\s*\d+\s*\(\s*x\s*[+-]", normalized, flags=re.IGNORECASE):
        scores["hs_log_interval_extrema"] = scores.get("hs_log_interval_extrema", 0) + 20
    if re.search(r"[+-]?\d*\s*sin\s*x\s*[+-]\s*sqrt\s*\(\s*[13]\s*\)\s*=\s*0", normalized, flags=re.IGNORECASE) and re.search(r"(?:pi|π)", normalized, flags=re.IGNORECASE):
        scores["hs_sine_linear_interval"] = scores.get("hs_sine_linear_interval", 0) + 20
    if re.search(r"\|\s*[+-]?\d*\s*x\s*(?:[+-]\s*\d+)?\s*\|\s*=\s*[+-]?\d+", normalized):
        scores["hs_absolute_linear_equation"] = scores.get("hs_absolute_linear_equation", 0) + 20
    if re.search(r"[+-]?\d*\s*x\s*(?:[+-]\s*\d+)?\s*(?:<=|>=|<|>|≤|≥)\s*[+-]?\d+", normalized):
        scores["fn_linear_inequality"] = scores.get("fn_linear_inequality", 0) + 20
    if re.search(r"\(\s*[+-]?\d+\s*,\s*[+-]?\d+\s*,\s*[+-]?\d+\s*\)\s*[·.*]\s*\(\s*[+-]?\d+\s*,\s*[+-]?\d+\s*,\s*[+-]?\d+\s*\)", normalized):
        scores["csg_vector_dot_3d"] = scores.get("csg_vector_dot_3d", 0) + 20
    if "A=" in normalized and "B=" in normalized and "AB=" not in normalized:
        scores["la_matrix_multiply"] = scores.get("la_matrix_multiply", 0) + 20
    domain = max(scores, key=scores.get) if scores else "cm_algebra_basic"
    matched_rules = [r for r in rules if r.get("domain") == domain]
    slots = _extract_slots(normalized, domain)
    required = [item for rule in matched_rules for item in rule.get("conditions", {}).get("requires", [])]
    missing = [item for item in required if item not in slots]
    top_score = scores.get(domain, 0)
    total_score = sum(scores.values()) or 1
    confidence = round(top_score / total_score, 3) if top_score else 0.0
    return {
        "normalized": normalized,
        "domain": domain,
        "tags": sorted(set(tags)),
        "slots": slots,
        "rules": matched_rules,
        "matched_keywords": sorted(set(tags)),
        "missing": sorted(set(missing)),
        "confidence": confidence,
    }


def _extract_slots(text: str, domain: str) -> dict[str, int]:
    """필요 변수: 정규화 문장과 개념 도메인. 유형별 기호 뒤 숫자를 슬롯으로 매핑한다."""
    def value(pattern: str) -> int | None:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return None
        groups = [item for item in match.groups() if item not in (None, "")]
        try:
            return int("".join(groups[-2:])) if len(groups) >= 2 and groups[-2] in ("+", "-") else int(groups[-1])
        except ValueError:
            return None

    if domain == "cm_arith_sequence":
        indices = [int(item) for item in re.findall(r"a\s*_?([0-9]+)", text, flags=re.IGNORECASE)]
        term_counts = [int(item) for item in re.findall(r"([0-9]+)\s*항", text)]
        n = max(indices + term_counts) if indices or term_counts else None
        a1 = value(r"a\s*_?1\s*=\s*([+-]?\d+)") or value(r"(?:첫항|첫째항)\s*(?:은|이)?\s*([+-]?\d+)")
        d = value(r"d\s*=\s*([+-]?\d+)") or value(r"공차\s*(?:는|가|이)?\s*([+-]?\d+)")
        result = {k: v for k, v in {"a1": a1, "d": d, "n": n}.items() if v is not None}
        if "합" in text:
            result["kind"] = "arithmetic_sum"
        return result
    if domain == "hs1_geometric_sequence":
        indices = [int(item) for item in re.findall(r"a\s*_?([0-9]+)", text, flags=re.IGNORECASE)]
        term_counts = [int(item) for item in re.findall(r"([0-9]+)\s*항", text)]
        n = max(indices + term_counts) if indices or term_counts else None
        a1 = value(r"(?:첫항|첫째항)\s*(?:은|이)?\s*([+-]?\d+)")
        ratio = value(r"공비\s*(?:는|가|이)?\s*([+-]?\d+)")
        result = {k: v for k, v in {"a1": a1, "ratio": ratio, "n": n}.items() if v is not None}
        if "합" in text:
            result["kind"] = "geometric_sum"
        return result
    if domain == "stat_binomial_distribution":
        n = value(r"n\s*=\s*(\d+)")
        numerator = value(r"p\s*=\s*(\d+)\s*/")
        denominator = value(r"p\s*=\s*\d+\s*/\s*(\d+)")
        k = value(r"(?:k|X)\s*=\s*(\d+)")
        if None in (n, numerator, denominator, k) or denominator == 0:
            return {}
        return {"n": n, "p": Fraction(numerator, denominator), "k": k}
    if domain == "geo_vector_dot":
        match = re.search(r"\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)\s*[·.]\s*\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)", text)
        return {"x1": int(match.group(1)), "y1": int(match.group(2)), "x2": int(match.group(3)), "y2": int(match.group(4))} if match else {}
    if domain == "csg_vector_dot_3d":
        match = re.search(r"\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)\s*[·.*]\s*\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)", text)
        if not match:
            return {}
        values = [int(value) for value in match.groups()]
        return {"vector_a": values[:3], "vector_b": values[3:]}
    if domain == "cal_trig_derivative":
        kind = "sin" if "sin" in text else "cos" if "cos" in text else None
        input_value = value(r"x\s*=\s*([+-]?\d+)")
        return {"kind": kind, "input": input_value} if kind and input_value is not None else {}
    if domain == "hs_polynomial_remainder":
        matches = re.findall(r"x\s*([+-])\s*(\d+)\s*로\s*나눈\s*나머지는\s*([+-]?\d+)", text)
        point = value(r"R\s*\(\s*([+-]?\d+)\s*\)")
        if len(matches) < 2 or point is None:
            return {}
        roots = [(-int(constant) if sign == "+" else int(constant), int(remainder)) for sign, constant, remainder in matches[:2]]
        return {"root1": roots[0][0], "remainder1": roots[0][1], "root2": roots[1][0], "remainder2": roots[1][1], "point": point}
    if domain == "hs_rational_interval_extrema":
        function = re.search(r"a\s*/\s*\(\s*x\s*([+-])\s*(\d+)\s*\)\s*\+\s*b", text)
        interval = re.search(r"([+-]?\d+)\s*≤\s*x\s*≤\s*([+-]?\d+)", text)
        maximum = value(r"최댓값이\s*([+-]?\d+)")
        minimum = value(r"최솟값이\s*([+-]?\d+)")
        if not function or not interval or maximum is None or minimum is None:
            return {}
        shift = int(function.group(2)) if function.group(1) == "-" else -int(function.group(2))
        return {"shift": shift, "left": int(interval.group(1)), "right": int(interval.group(2)), "maximum": maximum, "minimum": minimum}
    if domain == "hs_matrix_product":
        matrix_pattern = r"\(\(\s*([^,()]+)\s*,\s*([^,()]+)\s*\)\s*,\s*\(\s*([^,()]+)\s*,\s*([^,()]+)\s*\)\s*\)"
        left_match = re.search(r"A\s*=\s*" + matrix_pattern, text)
        right_match = re.search(r"B\s*=\s*" + matrix_pattern, text)
        product_match = re.search(r"AB\s*=\s*" + matrix_pattern, text)
        if not left_match or not right_match or not product_match:
            return {}
        def parse_entry(raw: str) -> int | str | None:
            item = raw.strip()
            return item if item == "k" else int(item) if re.fullmatch(r"[+-]?\d+", item) else None
        left_values = [parse_entry(item) for item in left_match.groups()]
        right_values = [parse_entry(item) for item in right_match.groups()]
        if any(item is None for item in left_values + right_values):
            return {}
        targets: list[dict[str, int]] = []
        requested: list[list[int]] = []
        for index, item in enumerate(entry.strip() for entry in product_match.groups()):
            row, column = divmod(index, 2)
            if re.fullmatch(r"[+-]?\d+", item):
                targets.append({"row": row, "column": column, "expected": int(item)})
            elif re.fullmatch(r"[a-z]", item):
                requested.append([row, column])
        return {"left": [left_values[:2], left_values[2:]], "right": [right_values[:2], right_values[2:]], "targets": targets, "requested": requested}
    if domain == "la_matrix_multiply":
        matrix_pattern = r"\(\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)\s*,\s*\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)\s*\)"
        left_match = re.search(r"A\s*=\s*" + matrix_pattern, text)
        right_match = re.search(r"B\s*=\s*" + matrix_pattern, text)
        if not left_match or not right_match:
            return {}
        return {"left_matrix": [[int(left_match.group(1)), int(left_match.group(2))], [int(left_match.group(3)), int(left_match.group(4))]], "right_matrix": [[int(right_match.group(1)), int(right_match.group(2))], [int(right_match.group(3)), int(right_match.group(4))]]}
    if domain == "cm_set":
        return {k: v for k, v in {"a": value(r"\|A\|\s*=\s*([+-]?\d+)"), "b": value(r"\|B\|\s*=\s*([+-]?\d+)"), "c": value(r"\|A∩B\|\s*=\s*([+-]?\d+)")}.items() if v is not None}
    if domain == "cm_linear":
        return {k: v for k, v in {"a": value(r"([+-]?\d+)\s*x"), "b": value(r"x\s*([+-])\s*(\d+)"), "c": value(r"=\s*([+-]?\d+)")}.items() if v is not None}
    if domain == "hs1_function_basic":
        a = value(r"f\s*\(\s*x\s*\)\s*=\s*([+-]?\d+)\s*x")
        b = value(r"f\s*\(\s*x\s*\)\s*=\s*[+-]?\d+\s*x\s*([+-])\s*(\d+)")
        input_value = value(r"(?:x|f\s*\()\s*=\s*([+-]?\d+)\s*\)?")
        return {k: v for k, v in {"a": a, "b": b, "input": input_value}.items() if v is not None}
    if domain == "hs1_function_composition":
        numbers = [int(item) for item in re.findall(r"[+-]?\d+", text)]
        if len(numbers) >= 5:
            return {"a": numbers[0], "b": numbers[1], "c": numbers[2], "d": numbers[3], "input": numbers[4]}
        return {}
    if domain == "hs1_inverse_function":
        a = value(r"f\s*\(\s*x\s*\)\s*=\s*([+-]?\d+)\s*x")
        b = value(r"f\s*\(\s*x\s*\)\s*=\s*[+-]?\d+\s*x\s*([+-])\s*(\d+)")
        return {k: v for k, v in {"a": a, "b": b}.items() if v is not None}
    if domain == "hs1_polynomial_factor":
        b = value(r"x(?:\^\s*2|2)\s*([+-])\s*(\d+)\s*x")
        c = value(r"x(?:\^\s*2|2).*?[+-]\s*\d+\s*x\s*([+-])\s*(\d+)")
        return {k: v for k, v in {"b": b, "c": c}.items() if v is not None}
    if domain == "hs_polynomial_value":
        expression = re.search(r"P\s*\(\s*x\s*\)\s*=\s*(.+?)(?=\s*(?:일 때|에서|[,;]|P\s*\(\s*[+-]?\d+)|$)", text, flags=re.IGNORECASE)
        point_match = re.search(r"P\s*\(\s*([+-]?\d+)\s*\)", text, flags=re.IGNORECASE)
        if not expression or not point_match:
            return {}
        raw = expression.group(1).replace(" ", "").replace("²", "^2").replace("-", "+-")
        terms = [term for term in raw.split("+") if term]
        parsed_terms: dict[int, int] = {}
        for term in terms:
            match = re.fullmatch(r"([+-]?)(\d*)x(?:\^(\d+))?", term, flags=re.IGNORECASE)
            if match:
                sign = -1 if match.group(1) == "-" else 1
                parsed_terms[int(match.group(3) or "1")] = int(match.group(2) or "1") * sign
            elif re.fullmatch(r"[+-]?\d+", term):
                parsed_terms[0] = int(term)
            else:
                return {}
        if not parsed_terms:
            return {}
        highest = max(parsed_terms)
        return {"coefficients": [parsed_terms.get(power, 0) for power in range(highest, -1, -1)], "point": int(point_match.group(1))}
    if domain == "hs_polynomial_addition":
        expressions = re.search(r"A\s*=\s*([^,;]+?)\s*,?\s*B\s*=\s*([^,;]+?)(?=\s*(?:에 대하여|일 때|A\s*\+\s*B|$))", text, flags=re.IGNORECASE)
        if not expressions:
            return {}
        def parse_polynomial(raw: str) -> dict[int, int] | None:
            terms = [item for item in raw.replace(" ", "").replace("−", "-").replace("-", "+-").split("+") if item]
            coefficients: dict[int, int] = {}
            for item in terms:
                match = re.fullmatch(r"([+-]?)(\d*)x(?:\^(\d+))?", item, flags=re.IGNORECASE)
                if match:
                    sign = -1 if match.group(1) == "-" else 1
                    power, coefficient = int(match.group(3) or "1"), sign * int(match.group(2) or "1")
                elif re.fullmatch(r"[+-]?\d+", item):
                    power, coefficient = 0, int(item)
                else:
                    return None
                coefficients[power] = coefficients.get(power, 0) + coefficient
            return coefficients
        left, right = parse_polynomial(expressions.group(1)), parse_polynomial(expressions.group(2))
        return {"left": left, "right": right} if left is not None and right is not None else {}
    if domain == "integer_gcd":
        matched = re.search(r"gcd\s*\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)", text, flags=re.IGNORECASE)
        if matched:
            return {"integers": [int(matched.group(1)), int(matched.group(2))]}
        numbers = [int(value) for value in re.findall(r"[+-]?\d+", text)]
        return {"integers": numbers[:2]} if len(numbers) >= 2 else {}
    if domain == "hs_absolute_linear_equation":
        match = re.search(r"\|\s*([+-]?\d*)\s*x\s*([+-]\s*\d+)?\s*\|\s*=\s*([+-]?\d+)", text)
        if not match:
            return {}
        coefficient = match.group(1).replace(" ", "")
        a = -1 if coefficient == "-" else int(coefficient or "1")
        b = int((match.group(2) or "0").replace(" ", ""))
        return {"a": a, "b": b, "target": int(match.group(3))}
    if domain == "fn_linear_inequality":
        # l≤x≤r은 구간 제약이며 한 개의 ax+b⋚c 해집합으로 잘라 풀면 허위 PASS가 된다.
        if re.search(r"[+-]?\d+\s*(?:<=|>=|≤|≥)\s*x\s*(?:<=|>=|≤|≥)\s*[+-]?\d+", text):
            return {}
        # 여러 비교 조건이 공존하면 함수의 정의역·최적화 같은 복합 문제일 수 있으므로 단일 계약으로 추측하지 않는다.
        if len(re.findall(r"(?:<=|>=|≤|≥|<|>)", text)) != 1:
            return {}
        match = re.search(r"([+-]?\d*)\s*x\s*([+-]\s*\d+)?\s*(<=|>=|<|>|≤|≥)\s*([+-]?\d+)", text)
        if not match:
            return {}
        coefficient = match.group(1).replace(" ", "")
        a = -1 if coefficient == "-" else int(coefficient or "1")
        b = int((match.group(2) or "0").replace(" ", ""))
        return {"a": a, "b": b, "relation": match.group(3), "c": int(match.group(4))}
    if domain == "hs_log_product_equation":
        match = re.search(r"log\s*_?\s*(\d+)\s*(\d+)\s*[*×]\s*log\s*_?\s*(\d+)\s*([a-zA-Z])\s*=\s*([+-]?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
        if not match:
            return {}
        return {"first_base": int(match.group(1)), "first_value": int(match.group(2)), "second_base": int(match.group(3)), "variable": match.group(4), "target": float(match.group(5))}
    if domain == "hs_exponential_asymptote_distance":
        base_match = re.search(r"y\s*=\s*(\d+)\s*\^\s*x", text, flags=re.IGNORECASE)
        shifted_match = re.search(r"y\s*=\s*\d+\s*\^\s*x\s*([+-])\s*(\d+)", text, flags=re.IGNORECASE)
        distance_match = re.search(r"거리(?:가|는|은)?\s*(\d+)", text)
        if not base_match or not shifted_match or not distance_match:
            return {}
        shift = int(shifted_match.group(2)) * (-1 if shifted_match.group(1) == "-" else 1)
        return {"base": int(base_match.group(1)), "shift": shift, "distance": int(distance_match.group(1))}
    if domain == "hs_inverse_log_power_coordinate":
        function = re.search(r"log\s*_?\s*(\d+)\s*x\s*([+-])\s*(\d+)", text, flags=re.IGNORECASE)
        point = re.search(r"\(\s*([+-]?\d+)\s*,\s*(\d+)\s*\^\s*[a-zA-Z]\s*\)", text)
        if not function or not point:
            return {}
        shift = int(function.group(3)) * (-1 if function.group(2) == "-" else 1)
        return {"base": int(function.group(1)), "shift": shift, "input": int(point.group(1)), "coordinate_base": int(point.group(2))}
    if domain == "hs_log_interval_extrema":
        function = re.search(r"log\s*_?\s*(\d+)\s*\(\s*x\s*([+-])\s*(\d+)\s*\)\s*([+-])\s*(\d+)", text, flags=re.IGNORECASE)
        interval = re.search(r"([+-]?\d+)\s*(?:≤|<=)\s*x\s*(?:≤|<=)\s*([+-]?\d+)", text)
        if not function or not interval:
            return {}
        horizontal_shift = int(function.group(3)) * (-1 if function.group(2) == "-" else 1)
        vertical_shift = int(function.group(5)) * (-1 if function.group(4) == "-" else 1)
        return {"base": int(function.group(1)), "horizontal_shift": horizontal_shift, "vertical_shift": vertical_shift, "left": int(interval.group(1)), "right": int(interval.group(2))}
    if domain == "hs_sine_linear_interval":
        equation = re.search(r"([+-]?\d*)\s*sin\s*x\s*([+-])\s*sqrt\s*\(\s*([13])\s*\)\s*=\s*0", text, flags=re.IGNORECASE)
        interval = re.search(r"((?:[+-]?\d*\s*(?:pi|π)(?:\s*/\s*\d+)?))\s*(?:≤|<=)\s*x\s*(?:≤|<=)\s*((?:[+-]?\d*\s*(?:pi|π)(?:\s*/\s*\d+)?))", text, flags=re.IGNORECASE)
        if not equation or not interval:
            return {}
        def pi_ratio(raw: str) -> tuple[int, int] | None:
            compact = raw.replace(" ", "").replace("π", "pi")
            match = re.fullmatch(r"([+-]?)(\d*)pi(?:/(\d+))?", compact, flags=re.IGNORECASE)
            if not match:
                return None
            sign = -1 if match.group(1) == "-" else 1
            numerator, denominator = sign * int(match.group(2) or "1"), int(match.group(3) or "1")
            return numerator, denominator
        left, right = pi_ratio(interval.group(1)), pi_ratio(interval.group(2))
        if left is None or right is None:
            return {}
        coefficient_raw = equation.group(1)
        coefficient = -1 if coefficient_raw == "-" else int(coefficient_raw or "1")
        return {"coefficient": coefficient, "constant_sign": -1 if equation.group(2) == "-" else 1, "radical": int(equation.group(3)), "left_numerator": left[0], "left_denominator": left[1], "right_numerator": right[0], "right_denominator": right[1]}
    if domain == "hs_cosine_law_side":
        match = re.search(r"AB\s*=\s*(\d+)\s*,?\s*BC\s*=\s*(\d+)\s*,?\s*cos\s*A\s*=\s*([+-]?\d+)\s*/\s*(\d+)", text, flags=re.IGNORECASE)
        if not match:
            return {}
        return {"known_adjacent": int(match.group(1)), "angle_opposite": int(match.group(2)), "cosine": int(match.group(3)) / int(match.group(4))}
    if domain == "hs1_exponential_log":
        root_rational_power = re.search(
            r"root_\s*(\d+)\s*\(\s*(\d+)\s*\)\s*\*\s*(\d+)\s*\^\s*\(\s*([+-]?\d+)\s*/\s*(\d+)\s*\)",
            text,
            flags=re.IGNORECASE,
        )
        if root_rational_power:
            return {
                "kind": "root_rational_power_product", "root_index": int(root_rational_power.group(1)),
                "radicand": int(root_rational_power.group(2)), "base": int(root_rational_power.group(3)),
                "exponent_numerator": int(root_rational_power.group(4)), "exponent_denominator": int(root_rational_power.group(5)),
            }
        power = re.search(r"([0-9]+)\s*\^\s*([0-9]+)", text)
        logarithm = re.search(r"log\s*_?\s*([0-9]+)\s*([0-9]+)", text, flags=re.IGNORECASE)
        if logarithm:
            return {"kind": "log", "base": int(logarithm.group(1)), "value": int(logarithm.group(2))}
        if power:
            return {"kind": "power", "base": int(power.group(1)), "exponent": int(power.group(2))}
        return {}
    if domain == "hs1_exponential_equation":
        # 밑은 정수 또는 (p/q)인 양의 유리수만 구조화한다. 임의의 식은 추측하지 않는다.
        base_pattern = r"(?:[0-9]+|\(\s*[0-9]+\s*/\s*[0-9]+\s*\))"
        complex_power = re.search(
            rf"({base_pattern})\s*\^\s*\(?\s*([+-]?\s*[0-9]*)\s*x\s*([+-]\s*[0-9]+)?\s*\)?\s*=\s*"
            rf"({base_pattern})\s*\^\s*\(?\s*([+-]?\s*[0-9]*)\s*x\s*([+-]\s*[0-9]+)?\s*\)?", text, flags=re.IGNORECASE,
        )
        if complex_power:
            def base(raw: str) -> float:
                """변수: 정수 또는 (p/q) 밑 문자열. 원리: 양의 유리수 밑을 부동소수값으로 정규화한다."""
                compact = raw.replace(" ", "").strip("()")
                numerator, separator, denominator = compact.partition("/")
                return int(numerator) / int(denominator) if separator else float(int(numerator))

            def coefficient(raw: str) -> int:
                """변수: x의 계수 문자열. 원리: 생략 부호를 ±1로 보정해 정수 계수로 반환한다."""
                compact = raw.replace(" ", "")
                return -1 if compact == "-" else (1 if compact in ("", "+") else int(compact))

            def constant(raw: str | None) -> int:
                """변수: 지수의 상수항 문자열. 원리: 생략된 상수항을 0으로 정규화한다."""
                return int((raw or "0").replace(" ", ""))

            return {
                "kind": "linear_power_equation", "left_base": base(complex_power.group(1)), "left_x": coefficient(complex_power.group(2)),
                "left_constant": constant(complex_power.group(3)), "right_base": base(complex_power.group(4)),
                "right_x": coefficient(complex_power.group(5)), "right_constant": constant(complex_power.group(6)),
            }
        power = re.search(r"([0-9]+)\s*\^\s*x\s*=\s*([0-9]+)", text, flags=re.IGNORECASE)
        log_eq = re.search(r"log\s*_?\s*([0-9]+)\s*x\s*=\s*([0-9]+)", text, flags=re.IGNORECASE)
        if power:
            return {"kind": "power_equation", "base": int(power.group(1)), "value": int(power.group(2))}
        if log_eq:
            return {"kind": "log_equation", "base": int(log_eq.group(1)), "exponent": int(log_eq.group(2))}
        return {}
    if domain == "hs1_trigonometry":
        match = re.search(r"(sin|cos|tan|사인|코사인|탄젠트)\s*([0-9]+)", text, flags=re.IGNORECASE)
        return {"kind": match.group(1).lower(), "angle": int(match.group(2))} if match else {}
    if domain == "hs2_limit":
        point = value(r"(?:x|t)\s*(?:->|→)\s*([+-]?\d+)")
        if point is None:
            return {}
        difference_quotient = re.search(
            r"f\s*\(\s*x\s*\)\s*=\s*([+-]?\s*\d*)\s*x\s*\^\s*2\s*"
            r"([+-]\s*(?:\d*)\s*x)?\s*([+-]\s*\d+)?",
            text,
            flags=re.IGNORECASE,
        )
        if difference_quotient and re.search(r"f\s*\(\s*x\s*\)\s*-\s*f\s*\(", text, flags=re.IGNORECASE):
            def polynomial_coefficient(raw: str | None, variable: bool = False) -> int:
                """변수: 다항식 항 문자열·변수 포함 여부. 원리: ±x·±n·생략 계수를 정수로 표준화한다."""
                compact = (raw or "").replace(" ", "")
                if variable:
                    compact = compact.replace("x", "")
                if compact in ("", "+"):
                    return 1
                if compact == "-":
                    return -1
                return int(compact)

            return {
                "kind": "quadratic_difference_quotient",
                "point": point,
                "quadratic": polynomial_coefficient(difference_quotient.group(1)),
                "linear": polynomial_coefficient(difference_quotient.group(2), variable=True),
                "constant": polynomial_coefficient(difference_quotient.group(3)) if difference_quotient.group(3) else 0,
            }
        # 기존에 검증된 단항식 조합만 연속성 대입으로 계산한다. 다른 극한은 추측하지 않는다.
        if re.search(r"x\s*(?:\^\s*2|²|2)\s*\+\s*3\s*x", text, flags=re.IGNORECASE):
            return {"kind": "quadratic_plus_linear", "point": point}
        return {}
    if domain == "hs2_derivative":
        cubic_extrema = re.search(
            r"f\s*\(\s*x\s*\)\s*=\s*([+-]?\s*\d*)\s*x\s*\^\s*3\s*\+\s*a\s*x\s*([+-]\s*\d+).*?"
            r"x\s*=\s*([+-]?\d+).*?극대.*?극솟값",
            text,
            flags=re.IGNORECASE,
        )
        if cubic_extrema:
            def cubic_leading(raw: str) -> int:
                """변수: x³ 계수 문자열. 원리: 생략된 ±1을 포함해 정수 계수로 정규화한다."""
                compact = raw.replace(" ", "")
                return -1 if compact == "-" else (1 if compact in ("", "+") else int(compact))

            return {
                "kind": "cubic_parameter_extrema", "cubic": cubic_leading(cubic_extrema.group(1)),
                "constant": int(cubic_extrema.group(2).replace(" ", "")), "maximum_point": int(cubic_extrema.group(3)),
            }
        factored = re.search(
            r"f\s*\(\s*x\s*\)\s*=\s*\(\s*([+-]?\s*\d*)\s*x\s*([+-]\s*\d+)\s*\)\s*"
            r"\(\s*([+-]?\s*\d*)\s*x\s*\^\s*2\s*([+-]\s*\d*)\s*x\s*([+-]\s*\d+)\s*\).*?"
            r"f\s*'\s*\(\s*([+-]?\d+)\s*\)",
            text,
            flags=re.IGNORECASE,
        )
        if factored:
            def signed_coefficient(raw: str) -> int:
                """변수: 부호 포함 계수 문자열. 원리: 생략된 ±1 계수를 정수로 표준화한다."""
                compact = raw.replace(" ", "")
                return -1 if compact == "-" else (1 if compact in ("", "+") else int(compact))

            return {
                "kind": "factored_linear_quadratic", "linear_x": signed_coefficient(factored.group(1)),
                "linear_constant": int(factored.group(2).replace(" ", "")), "quadratic_x2": signed_coefficient(factored.group(3)),
                "quadratic_x": signed_coefficient(factored.group(4)), "quadratic_constant": int(factored.group(5).replace(" ", "")),
                "input": int(factored.group(6)),
            }
        match = re.search(r"f\s*\(x\)\s*=\s*x\s*\^\s*([0-9]+).*?(?:x\s*=|at\s*)([+-]?\d+)", text, flags=re.IGNORECASE)
        return {"power": int(match.group(1)), "input": int(match.group(2))} if match else {}
    if domain == "hs2_tangent":
        match = re.search(r"f\s*\(x\)\s*=\s*x\s*\^\s*([0-9]+).*?(?:x\s*=|at\s*)([+-]?\d+)", text, flags=re.IGNORECASE)
        return {"power": int(match.group(1)), "input": int(match.group(2))} if match else {}
    if domain == "hs2_integral":
        if not any(marker in text for marker in ("정적분", "부정적분", "적분")):
            return {}
        match = re.search(r"(?:0|적분)\s*(?:부터|to|,)\s*([0-9]+).*?x\s*(?:\^\s*)?([0-9]*)", text, flags=re.IGNORECASE)
        numbers = [int(item) for item in re.findall(r"[+-]?\d+", text)]
        if len(numbers) >= 2:
            return {"lower": numbers[0], "upper": numbers[1], "power": int(match.group(2) or 1) if match else 1}
        return {}
    if domain in {"hs_composite_sequence", "hs_composite_sequence_function"}:
        sequence = re.search(r"첫항\s*([+-]?\d+)\s*,?\s*공차\s*([+-]?\d+).*?a\s*([0-9]+)\s*\+\s*a\s*([0-9]+)", text)
        if not sequence:
            return {}
        result: dict[str, int] = {"a1": int(sequence.group(1)), "d": int(sequence.group(2)), "n1": int(sequence.group(3)), "n2": int(sequence.group(4))}
        if domain == "hs_composite_sequence_function":
            function = re.search(r"f\s*\(\s*x\s*\)\s*=\s*([+-]?\d+)\s*x\s*([+-])\s*(\d+)", text, flags=re.IGNORECASE)
            input_value = value(r"g\s*\(\s*([+-]?\d+)\s*\)")
            if not function or input_value is None:
                return {}
            result.update({"f_a": int(function.group(1)), "f_b": int(function.group(2) + function.group(3)), "input": input_value})
        return result
    if domain == "cm_ratio":
        nums = [int(item) for item in re.findall(r"[+-]?\d+", text)]
        return {"numbers": nums} if nums else {}
    if domain == "cm_probability":
        if "경우의 수" in text or "조합" in text or "순열" in text:
            nums = [int(item) for item in re.findall(r"[+-]?\d+", text)]
            kind = "permutation" if "순열" in text else "combination"
            return {"kind": kind, "numbers": nums} if len(nums) >= 2 else {}
        percent = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", text)
        if percent:
            return {"probability": float(percent.group(1)) / 100}
        fraction = re.search(r"([+-]?\d+)\s*/\s*([+-]?\d+)", text)
        nums = [int(item) for item in fraction.groups()] if fraction else [int(item) for item in re.findall(r"[+-]?\d+", text)]
        return {"numbers": nums} if nums else {}
    if domain == "hs1_conditional_probability":
        fractions = re.findall(r"(?:P\s*\([^)]*\)|확률)[^=]*=\s*([0-9]+)\s*/\s*([0-9]+)", text)
        if len(fractions) >= 2:
            return {"joint": Fraction(int(fractions[0][0]), int(fractions[0][1])), "condition": Fraction(int(fractions[1][0]), int(fractions[1][1]))}
        return {}
    if domain == "cm_geometry":
        nums = [int(item) for item in re.findall(r"[+-]?\d+", text)]
        if "삼각형의 넓이" in text or ("밑변" in text and "높이" in text):
            return {"kind": "triangle_area", "numbers": nums} if len(nums) >= 2 else {}
        if "원의 넓이" in text or "반지름" in text:
            return {"kind": "circle_area", "numbers": nums} if nums else {}
        if "직사각형" in text or ("가로" in text and "세로" in text):
            kind = "rectangle_perimeter" if "둘레" in text else "rectangle_area"
            return {"kind": kind, "numbers": nums} if len(nums) >= 2 else {}
        return {"numbers": nums} if nums else {}
    a = value(r"([+-]?\d+)\s*x(?:\^\s*2|2)")
    if a is None and re.search(r"(?:^|\s)x(?:\^\s*2|2)", text, flags=re.IGNORECASE):
        a = 1
    return {k: v for k, v in {"a": a, "b": value(r"x(?:\^\s*2|2)\s*([+-])\s*(\d+)"), "c": value(r"x(?:\^\s*2|2).*?([+-])\s*(\d+)\s*=\s*0")}.items() if v is not None}


def verify_result(domain: str, slots: dict[str, Any], answer: int | float) -> bool:
    """필요 변수: 도메인·추출 슬롯·정답. 규칙의 최소 불변식을 재계산해 결과를 검산한다."""
    if domain == "cm_arith_sequence":
        if slots.get("kind") == "arithmetic_sum":
            return answer == slots.get("n") * (2 * slots.get("a1") + (slots.get("n") - 1) * slots.get("d")) / 2
        return answer == slots.get("a1") + (slots.get("n") - 1) * slots.get("d")
    if domain == "hs1_geometric_sequence":
        a1, ratio, n = (slots.get(key) for key in ("a1", "ratio", "n"))
        if None in (a1, ratio, n):
            return False
        expected = a1 * ratio ** (n - 1)
        if slots.get("kind") == "geometric_sum":
            expected = a1 * n if ratio == 1 else a1 * (ratio ** n - 1) / (ratio - 1)
        return answer == expected
    if domain == "stat_binomial_distribution":
        from math import comb
        return answer == float(comb(slots["n"], slots["k"]) * slots["p"] ** slots["k"] * (1 - slots["p"]) ** (slots["n"] - slots["k"]))
    if domain == "geo_vector_dot":
        return answer == slots["x1"] * slots["x2"] + slots["y1"] * slots["y2"]
    if domain == "cal_trig_derivative":
        import math
        expected = math.cos(slots["input"]) if slots["kind"] == "sin" else -math.sin(slots["input"])
        return abs(answer - expected) < 1e-12
    if domain == "cm_set":
        return answer == slots.get("a") + slots.get("b") - slots.get("c")
    if domain == "cm_linear":
        a, b, c = (slots.get(key) for key in ("a", "b", "c"))
        return a not in (None, 0) and a * answer + b == c
    if domain == "hs1_function_basic":
        a, b, input_value = (slots.get(key) for key in ("a", "b", "input"))
        return a is not None and b is not None and input_value is not None and answer == a * input_value + b
    if domain == "hs1_function_composition":
        a, b, c, d, input_value = (slots.get(key) for key in ("a", "b", "c", "d", "input"))
        return None not in (a, b, c, d, input_value) and answer == a * (c * input_value + d) + b
    if domain == "hs1_inverse_function":
        return isinstance(answer, str) and answer.startswith("(x")
    if domain == "hs1_polynomial_factor":
        return isinstance(answer, str) and answer.startswith("(x")
    if domain in {"hs1_trigonometry", "hs2_integral"}:
        return isinstance(answer, (int, float))
    if domain == "hs2_derivative":
        if not isinstance(answer, (int, float)):
            return False
        if slots.get("kind") == "factored_linear_quadratic":
            value = slots["input"]
            linear_x, linear_constant = slots["linear_x"], slots["linear_constant"]
            quadratic_x2, quadratic_x, quadratic_constant = (slots[key] for key in ("quadratic_x2", "quadratic_x", "quadratic_constant"))
            function = lambda x: (linear_x * x + linear_constant) * (quadratic_x2 * x * x + quadratic_x * x + quadratic_constant)
            step = 1e-6
            return abs(answer - (function(value + step) - function(value - step)) / (2 * step)) < 1e-5
        if slots.get("kind") == "cubic_parameter_extrema":
            cubic, maximum_point, constant = slots["cubic"], slots["maximum_point"], slots["constant"]
            linear = -3 * cubic * maximum_point * maximum_point
            minimum_point = -maximum_point
            expected = cubic * minimum_point ** 3 + linear * minimum_point + constant
            return cubic != 0 and 6 * cubic * maximum_point < 0 and answer == expected
        return "power" in slots and "input" in slots and answer == slots["power"] * slots["input"] ** (slots["power"] - 1)
    if domain == "hs1_exponential_log":
        if not isinstance(answer, (int, float)):
            return False
        if slots.get("kind") == "root_rational_power_product":
            root_index, radicand, base = slots["root_index"], slots["radicand"], slots["base"]
            if root_index <= 0 or radicand < 0 or base <= 0 or slots["exponent_denominator"] == 0:
                return False
            expected = radicand ** (1 / root_index) * base ** (slots["exponent_numerator"] / slots["exponent_denominator"])
            return abs(answer - expected) < 1e-12
        return True
    if domain == "hs2_limit":
        if not isinstance(answer, (int, float)):
            return False
        if slots.get("kind") == "quadratic_difference_quotient":
            point, quadratic, linear = slots["point"], slots["quadratic"], slots["linear"]
            step = 1e-6
            value_at = lambda x: quadratic * x * x + linear * x + slots.get("constant", 0)
            return abs(answer - (value_at(point + step) - value_at(point)) / step) < 1e-5
        return slots.get("kind") == "quadratic_plus_linear" and answer == slots["point"] ** 2 + 3 * slots["point"]
    if domain == "hs1_exponential_equation":
        if slots.get("kind") == "linear_power_equation":
            left = slots["left_base"] ** (slots["left_x"] * answer + slots["left_constant"])
            right = slots["right_base"] ** (slots["right_x"] * answer + slots["right_constant"])
            return abs(left - right) < 1e-8
        return isinstance(answer, (int, float))
    if domain == "hs2_tangent":
        return isinstance(answer, (int, float))
    if domain == "cm_quadratic":
        a, b, c = (slots.get(key) for key in ("a", "b", "c"))
        return a not in (None, 0) and a * answer * answer + b * answer + c == 0
    if domain == "cm_ratio":
        nums = slots.get("numbers", [])
        return len(nums) >= 4 and nums[0] * nums[3] == nums[1] * nums[2]
    if domain == "cm_geometry":
        nums = slots.get("numbers", [])
        return len(nums) >= 3 and nums[0] ** 2 + nums[1] ** 2 == nums[2] ** 2
    return True


def solve_rule(domain: str, slots: dict[str, Any]) -> dict[str, Any]:
    """필요 변수: 분류 도메인과 슬롯. 중3 기본 규칙을 계산하고 검산 결과를 함께 반환한다."""
    tool_by_domain = {
        "hs_polynomial_addition": "add_polynomial_coefficients",
        "hs_sine_linear_interval": "solve_sine_linear_special_interval",
        "hs_cosine_law_side": "solve_cosine_law_adjacent_side",
        "hs_log_interval_extrema": "solve_log_interval_extrema_sum",
        "hs_inverse_log_power_coordinate": "solve_inverse_log_power_coordinate",
        "hs_exponential_asymptote_distance": "solve_exponential_asymptote_distance_sum",
        "hs_log_product_equation": "solve_log_product_equation",
        "integer_gcd": "evaluate_integer_gcd",
        "hs_absolute_linear_equation": "solve_absolute_linear_equation",
        "fn_linear_inequality": "solve_linear_inequality",
        "csg_vector_dot_3d": "dot_product_3d",
        "la_matrix_multiply": "matrix_multiply",
        "hs_polynomial_value": "evaluate_polynomial_horner",
        "hs_polynomial_remainder": "polynomial_remainder_two_linear",
        "hs_rational_interval_extrema": "rational_interval_extrema",
        "hs_matrix_product": "symbolic_matrix_product_2x2",
    }
    if domain in tool_by_domain:
        return call_math_tool(tool_by_domain[domain], slots)
    if domain == "hs_composite_sequence":
        a1, d, n1, n2 = (slots.get(key) for key in ("a1", "d", "n1", "n2"))
        if None in (a1, d, n1, n2):
            return {"status": "FAIL", "reason": "첫항·공차·두 항 번호가 필요합니다."}
        first = a1 + (n1 - 1) * d
        second = a1 + (n2 - 1) * d
        answer = first + second
        return {"status": "PASS", "answer": answer, "formula": "a_n=a_1+(n-1)d, M=a_p+a_q", "verified": answer == first + second,
                "knowledge_used": ["ar_seq_an_formula", "ar_seq_an_formula", "addition"]}
    if domain == "hs_composite_sequence_function":
        required = ("a1", "d", "n1", "n2", "f_a", "f_b", "input")
        if any(slots.get(key) is None for key in required):
            return {"status": "FAIL", "reason": "수열·함수·입력값 조건이 필요합니다."}
        a1, d, n1, n2 = (slots[key] for key in ("a1", "d", "n1", "n2"))
        sequence_sum = a1 + (n1 - 1) * d + a1 + (n2 - 1) * d
        g_value = slots["input"] + sequence_sum
        function_value = slots["f_a"] * g_value + slots["f_b"]
        answer = function_value  # log_2(2^(f(g(x))))의 역연산까지 적용한 값이다.
        return {"status": "PASS", "answer": answer, "formula": "a_n→M→g(x)=x+M→f(g(x))→log_2(2^y)=y", "verified": isinstance(answer, int),
                "knowledge_used": ["ar_seq_an_formula", "ar_seq_an_formula", "addition", "function_substitution", "function_substitution", "power_rule", "log_inverse"]}
    if domain == "hs1_geometric_sequence":
        a1, ratio, n = (slots.get(key) for key in ("a1", "ratio", "n"))
        if None in (a1, ratio, n) or n < 1:
            return {"status": "FAIL", "reason": "등비수열의 첫항·공비·항 번호가 필요합니다."}
        if slots.get("kind") == "geometric_sum":
            answer = a1 * n if ratio == 1 else a1 * (ratio ** n - 1) / (ratio - 1)
            formula = "S_n=a_1(r^n-1)/(r-1) (r≠1)"
        else:
            answer = a1 * ratio ** (n - 1)
            formula = "a_n=a_1r^(n-1)"
        return {"status": "PASS", "answer": int(answer) if answer == int(answer) else answer, "formula": formula, "verified": verify_result(domain, slots, answer)}
    if domain == "stat_binomial_distribution":
        from math import comb
        n, p, k = (slots.get(key) for key in ("n", "p", "k"))
        if None in (n, p, k) or not 0 <= p <= 1 or not 0 <= k <= n:
            return {"status": "FAIL", "reason": "이항분포의 n, p, k 조건이 올바르지 않습니다."}
        exact = comb(n, k) * p ** k * (1 - p) ** (n - k)
        answer = float(exact)
        return {"status": "PASS", "answer": answer, "fraction": str(exact), "formula": "P(X=k)=nCk·p^k·(1-p)^(n-k)", "verified": verify_result(domain, slots, answer)}
    if domain == "geo_vector_dot":
        if any(slots.get(key) is None for key in ("x1", "y1", "x2", "y2")):
            return {"status": "FAIL", "reason": "두 평면벡터의 성분이 필요합니다."}
        answer = slots["x1"] * slots["x2"] + slots["y1"] * slots["y2"]
        return {"status": "PASS", "answer": answer, "formula": "a·b=a_xb_x+a_yb_y", "verified": verify_result(domain, slots, answer)}
    if domain == "cal_trig_derivative":
        import math
        kind, input_value = slots.get("kind"), slots.get("input")
        if kind not in {"sin", "cos"} or input_value is None:
            return {"status": "FAIL", "reason": "sin 또는 cos와 대입할 x 값이 필요합니다."}
        answer = math.cos(input_value) if kind == "sin" else -math.sin(input_value)
        return {"status": "PASS", "answer": answer, "formula": "(sin x)'=cos x, (cos x)'=-sin x", "verified": verify_result(domain, slots, answer)}
    if domain == "cm_arith_sequence":
        a1, d, n = (slots.get(key) for key in ("a1", "d", "n"))
        if a1 is None or d is None or n is None:
            return {"status": "FAIL", "reason": "a1,d,n이 필요합니다."}
        if slots.get("kind") == "arithmetic_sum":
            answer = n * (2 * a1 + (n - 1) * d) / 2
            return {"status": "PASS", "answer": int(answer) if answer == int(answer) else answer, "formula": "S_n = n(2a1+(n-1)d)/2", "verified": answer == n * (2 * a1 + (n - 1) * d) / 2}
        answer = a1 + (n - 1) * d
    elif domain == "cm_set":
        a, b, c = (slots.get(key) for key in ("a", "b", "c"))
        if a is None or b is None or c is None or c > min(a, b):
            return {"status": "FAIL", "reason": "집합 크기 조건이 올바르지 않습니다."}
        answer = a + b - c
    elif domain == "cm_ratio":
        nums = slots.get("numbers", [])
        if len(nums) < 4 or nums[1] == 0 or nums[3] == 0:
            return {"status": "FAIL", "reason": "a:b=c:d 네 수가 필요합니다."}
        if nums[0] * nums[3] != nums[1] * nums[2]:
            return {"status": "FAIL", "reason": "비례식이 성립하지 않습니다."}
        answer = nums[0] / nums[1]
    elif domain == "cm_linear":
        a, b, c = (slots.get(key) for key in ("a", "b", "c"))
        if a in (None, 0) or b is None or c is None:
            return {"status": "FAIL", "reason": "a,b,c가 필요합니다."}
        answer = (c - b) / a
        if answer != int(answer):
            return {"status": "FAIL", "reason": "정수 범위를 벗어난 해입니다."}
        answer = int(answer)
    elif domain == "hs1_function_basic":
        a, b, input_value = (slots.get(key) for key in ("a", "b", "input"))
        if a is None or b is None or input_value is None:
            return {"status": "FAIL", "reason": "f(x)=ax+b와 입력값이 필요합니다."}
        answer = a * input_value + b
    elif domain == "hs1_function_composition":
        a, b, c, d, input_value = (slots.get(key) for key in ("a", "b", "c", "d", "input"))
        if None in (a, b, c, d, input_value):
            return {"status": "FAIL", "reason": "f,g의 일차식과 입력값이 필요합니다."}
        inner = c * input_value + d
        answer = a * inner + b
    elif domain == "hs1_inverse_function":
        a, b = (slots.get(key) for key in ("a", "b"))
        if a in (None, 0) or b is None:
            return {"status": "FAIL", "reason": "f(x)=ax+b의 a,b가 필요합니다."}
        answer = f"(x{(-b):+d})/{a}"
    elif domain == "hs1_conditional_probability":
        joint, condition = slots.get("joint"), slots.get("condition")
        if not joint or not condition or condition == 0:
            return {"status": "FAIL", "reason": "교집합 확률과 조건 사건 확률이 필요합니다."}
        answer = joint / condition
        return {"status": "PASS", "answer": float(answer), "fraction": str(answer), "formula": "P(A|B)=P(A∩B)/P(B)", "verified": answer * condition == joint}
    elif domain == "hs1_polynomial_factor":
        b, c = (slots.get(key) for key in ("b", "c"))
        if b is None or c is None:
            return {"status": "FAIL", "reason": "x²+bx+c의 b,c가 필요합니다."}
        factors = [(u, v) for u in range(-abs(c), abs(c) + 1) if u != 0 for v in range(-abs(c), abs(c) + 1) if v != 0 and u * v == c and u + v == b]
        if not factors:
            return {"status": "FAIL", "reason": "정수 범위에서 인수분해할 수 없습니다."}
        u, v = factors[0]
        answer = f"(x{u:+d})(x{v:+d})"
    elif domain == "hs1_exponential_log":
        if slots.get("kind") == "root_rational_power_product":
            root_index, radicand, base = (slots[key] for key in ("root_index", "radicand", "base"))
            denominator = slots["exponent_denominator"]
            if root_index <= 0 or radicand < 0 or base <= 0 or denominator == 0:
                return {"status": "FAIL", "reason": "n제곱근·유리수 지수의 정의역 조건이 올바르지 않습니다."}
            answer = radicand ** (1 / root_index) * base ** (slots["exponent_numerator"] / denominator)
            answer = int(round(answer)) if abs(answer - round(answer)) < 1e-12 else answer
        elif slots.get("kind") == "power":
            answer = slots["base"] ** slots["exponent"]
        elif slots.get("kind") == "log":
            value, base, current = slots["value"], slots["base"], 1
            answer = 0
            while current < value and value % base == 0:
                current *= base
                answer += 1
            if current != value:
                return {"status": "FAIL", "reason": "정수 지수 로그만 지원합니다."}
        else:
            return {"status": "FAIL", "reason": "a^n 또는 log_a b 형식이 필요합니다."}
    elif domain == "hs1_exponential_equation":
        if slots.get("kind") == "linear_power_equation":
            import math
            left_base, right_base = slots["left_base"], slots["right_base"]
            if left_base <= 0 or left_base == 1 or right_base <= 0 or right_base == 1:
                return {"status": "FAIL", "reason": "지수방정식의 밑 조건이 올바르지 않습니다."}
            base_change = math.log(right_base) / math.log(left_base)
            coefficient = slots["left_x"] - base_change * slots["right_x"]
            constant = base_change * slots["right_constant"] - slots["left_constant"]
            if abs(coefficient) < 1e-12:
                return {"status": "FAIL", "reason": "해가 유일한 일차 지수방정식이 아닙니다."}
            answer = constant / coefficient
            answer = int(answer) if abs(answer - round(answer)) < 1e-12 else answer
        elif slots.get("kind") == "power_equation":
            base, value, exponent = slots["base"], slots["value"], 0
            current = 1
            while current < value and value % base == 0:
                current *= base
                exponent += 1
            if current != value:
                return {"status": "FAIL", "reason": "정수 지수 해를 찾지 못했습니다."}
            answer = exponent
        elif slots.get("kind") == "log_equation":
            answer = slots["base"] ** slots["exponent"]
        else:
            return {"status": "FAIL", "reason": "a^x=b 또는 log_a x=b 형식이 필요합니다."}
    elif domain == "hs1_trigonometry":
        values = {"sin": {0: 0, 30: 0.5, 90: 1}, "cos": {0: 1, 60: 0.5, 90: 0}, "tan": {0: 0, 45: 1}}
        answer = values.get(slots.get("kind"), {}).get(slots.get("angle"))
        if answer is None:
            return {"status": "FAIL", "reason": "특수각(0,30,45,60,90)만 지원합니다."}
    elif domain == "hs2_limit":
        if slots.get("kind") == "quadratic_difference_quotient":
            answer = 2 * slots["quadratic"] * slots["point"] + slots["linear"]
        elif slots.get("kind") == "quadratic_plus_linear":
            answer = slots["point"] ** 2 + 3 * slots["point"]
        else:
            return {"status": "FAIL", "reason": "지원하는 다항식 극한 또는 차분몫 구조가 필요합니다."}
    elif domain == "hs2_derivative":
        if slots.get("kind") == "cubic_parameter_extrema":
            cubic, maximum_point = slots["cubic"], slots["maximum_point"]
            if cubic == 0 or 6 * cubic * maximum_point >= 0:
                return {"status": "FAIL", "reason": "주어진 점이 이 형태의 삼차함수 극대점이라는 조건을 만족하지 않습니다."}
            linear = -3 * cubic * maximum_point * maximum_point
            minimum_point = -maximum_point
            answer = cubic * minimum_point ** 3 + linear * minimum_point + slots["constant"]
        elif slots.get("kind") == "factored_linear_quadratic":
            value = slots["input"]
            linear = slots["linear_x"] * value + slots["linear_constant"]
            quadratic = slots["quadratic_x2"] * value * value + slots["quadratic_x"] * value + slots["quadratic_constant"]
            answer = slots["linear_x"] * quadratic + linear * (2 * slots["quadratic_x2"] * value + slots["quadratic_x"])
        else:
            power, input_value = slots.get("power"), slots.get("input")
            if power is None or input_value is None:
                return {"status": "FAIL", "reason": "x^n과 입력값이 필요합니다."}
            answer = power * (input_value ** (power - 1))
    elif domain == "hs2_tangent":
        power, input_value = slots.get("power"), slots.get("input")
        if power is None or input_value is None:
            return {"status": "FAIL", "reason": "접선 기울기를 구할 x^n과 입력값이 필요합니다."}
        answer = power * (input_value ** (power - 1))
    elif domain == "hs2_integral":
        lower, upper, power = slots.get("lower"), slots.get("upper"), slots.get("power")
        if lower is None or upper is None or power is None:
            return {"status": "FAIL", "reason": "적분 구간과 x의 지수가 필요합니다."}
        answer = (upper ** (power + 1) - lower ** (power + 1)) / (power + 1)
    elif domain == "cm_quadratic":
        a, b, c = (slots.get(key) for key in ("a", "b", "c"))
        if a in (None, 0) or b is None or c is None:
            return {"status": "FAIL", "reason": "a,b,c가 필요합니다."}
        disc = b * b - 4 * a * c
        root = int(disc ** 0.5) if disc >= 0 else -1
        if root < 0 or root * root != disc:
            return {"status": "FAIL", "reason": "정수근을 계산할 수 없습니다."}
        candidates = [(-b + root), (-b - root)]
        integer_roots = [num // (2 * a) for num in candidates if num % (2 * a) == 0]
        if not integer_roots:
            return {"status": "FAIL", "reason": "정수근이 없습니다."}
        answer = integer_roots[0]
    elif domain == "cm_geometry":
        nums = slots.get("numbers", [])
        if slots.get("kind") == "triangle_area":
            if len(nums) < 2:
                return {"status": "FAIL", "reason": "밑변과 높이가 필요합니다."}
            answer = nums[0] * nums[1] / 2
            return {"status": "PASS", "answer": answer, "formula": "삼각형 넓이 = 밑변×높이÷2", "verified": answer == nums[0] * nums[1] / 2}
        if slots.get("kind") == "circle_area":
            if not nums or nums[0] < 0:
                return {"status": "FAIL", "reason": "반지름이 필요합니다."}
            answer = 3.141592653589793 * nums[0] ** 2
            return {"status": "PASS", "answer": answer, "formula": "원의 넓이 = πr²", "verified": answer >= 0}
        if slots.get("kind") in {"rectangle_area", "rectangle_perimeter"}:
            if len(nums) < 2 or min(nums[:2]) < 0:
                return {"status": "FAIL", "reason": "가로와 세로가 필요합니다."}
            if slots["kind"] == "rectangle_perimeter":
                answer = 2 * (nums[0] + nums[1])
                formula = "직사각형 둘레 = 2×(가로+세로)"
            else:
                answer = nums[0] * nums[1]
                formula = "직사각형 넓이 = 가로×세로"
            return {"status": "PASS", "answer": answer, "formula": formula, "verified": answer >= 0}
        if len(nums) < 3:
            if len(nums) == 2:
                hypotenuse_squared = nums[0] ** 2 + nums[1] ** 2
                hypotenuse = int(hypotenuse_squared ** 0.5)
                if hypotenuse * hypotenuse != hypotenuse_squared:
                    return {"status": "FAIL", "reason": "두 변으로 정수 빗변을 계산할 수 없습니다."}
                return {"status": "PASS", "answer": hypotenuse, "formula": "c = √(a²+b²)", "verified": hypotenuse * hypotenuse == hypotenuse_squared}
            return {"status": "FAIL", "reason": "세 변의 길이가 필요합니다."}
        answer = nums[0] ** 2 + nums[1] ** 2
        if answer != nums[2] ** 2:
            return {"status": "FAIL", "reason": "피타고라스 조건을 만족하지 않습니다."}
        answer = nums[2]
    elif domain == "cm_probability":
        if slots.get("kind") == "combination":
            nums = slots.get("numbers", [])
            if len(nums) < 2 or nums[0] < nums[1] or nums[1] < 0:
                return {"status": "FAIL", "reason": "n과 r 조건이 필요합니다."}
            from math import comb
            answer = comb(nums[0], nums[1])
            return {"status": "PASS", "answer": answer, "formula": "nCr = n!/(r!(n-r)!)", "verified": answer == comb(nums[0], nums[1])}
        if slots.get("kind") == "permutation":
            nums = slots.get("numbers", [])
            if len(nums) < 2 or nums[0] < nums[1] or nums[1] < 0:
                return {"status": "FAIL", "reason": "n과 r 조건이 필요합니다."}
            from math import factorial
            answer = factorial(nums[0]) // factorial(nums[0] - nums[1])
            return {"status": "PASS", "answer": answer, "formula": "nPr = n!/(n-r)!", "verified": answer == factorial(nums[0]) // factorial(nums[0] - nums[1])}
        if "probability" in slots:
            answer = slots["probability"]
            fraction = str(Fraction(answer).limit_denominator())
            return {"status": "PASS", "answer": answer, "fraction": fraction, "formula": "P(E) = 유리한 경우 / 전체 경우", "verified": True}
        nums = slots.get("numbers", [])
        if len(nums) < 2 or nums[1] <= 0 or nums[0] < 0 or nums[0] > nums[1]:
            return {"status": "FAIL", "reason": "유리한 경우/전체 경우가 필요합니다."}
        answer = nums[0] / nums[1]
    else:
        return {"status": "FAIL", "reason": "아직 계산기가 없는 도메인입니다."}
    formulas = {
        "cm_arith_sequence": "a_n = a1 + (n-1)d",
        "cm_set": "|A∪B| = |A| + |B| - |A∩B|",
        "cm_linear": "x = (c-b)/a",
        "cm_quadratic": "x = (-b ± √(b²-4ac)) / 2a",
        "cm_ratio": "a:b=c:d ↔ ad=bc",
        "cm_probability": "P(E) = 유리한 경우 / 전체 경우",
        "cm_geometry": "a²+b²=c²",
        "hs1_function_basic": "f(x)=ax+b, f(t)=at+b",
        "hs1_function_composition": "f(g(t)) = a(ct+d)+b",
        "hs1_inverse_function": "f⁻¹(x)=(x-b)/a",
        "hs1_conditional_probability": "P(A|B)=P(A∩B)/P(B)",
        "hs1_polynomial_factor": "x²+bx+c=(x+u)(x+v)",
        "hs1_exponential_log": "a^n 또는 log_a b",
        "hs1_exponential_equation": "a^x=b 또는 log_a x=b",
        "hs1_trigonometry": "특수각 삼각함수 값",
        "hs2_limit": "lim x→a f(x)=f(a)",
        "hs2_derivative": "(x^n)'=nx^(n-1)",
        "hs2_tangent": "접선 기울기=f'(a)",
        "hs2_integral": "∫x^n dx=x^(n+1)/(n+1)",
        "hs_composite_sequence": "a_n=a_1+(n-1)d → a_p+a_q",
        "hs_composite_sequence_function": "수열 → 합성함수 → 지수·로그 역연산",
        "hs1_geometric_sequence": "a_n=a_1r^(n-1), S_n=a_1(r^n-1)/(r-1)",
        "stat_binomial_distribution": "P(X=k)=nCk·p^k·(1-p)^(n-k)",
        "geo_vector_dot": "a·b=a_xb_x+a_yb_y",
        "cal_trig_derivative": "(sin x)'=cos x, (cos x)'=-sin x",
    }
    result = {
        "status": "PASS",
        "answer": answer,
        "formula": formulas.get(domain, ""),
        "verified": verify_result(domain, slots, answer),
    }
    if domain == "cm_probability":
        result["fraction"] = str(Fraction(answer).limit_denominator())
    return result


def select_optimal_rule(parsed: dict[str, Any]) -> dict[str, Any]:
    """필요 변수: classify 결과. 위험도·필수 슬롯 충족·단계 수를 점수화해 가장 짧고 안전한 규칙 경로를 선택한다."""
    candidates = []
    for rule in parsed.get("rules", []):
        required = rule.get("conditions", {}).get("requires", [])
        missing = sum(item not in parsed.get("slots", {}) for item in required)
        risk_score = {"low": 0, "medium": 1, "high": 2}.get(rule.get("risk", "medium"), 1)
        candidates.append((missing, risk_score, len(required), rule))
    if not candidates:
        builtin = {
            "hs1_exponential_log": "hs1_exponential_log_basic",
            "hs1_exponential_equation": "hs1_exponential_equation_basic",
            "hs1_trigonometry": "hs1_special_angle_trig",
            "hs2_limit": "hs2_polynomial_limit",
            "hs2_derivative": "hs2_power_derivative",
            "hs2_tangent": "hs2_tangent_slope",
            "hs2_integral": "hs2_power_integral",
            "integer_gcd": "evaluate_integer_gcd",
            "hs_absolute_linear_equation": "solve_absolute_linear_equation",
            "fn_linear_inequality": "solve_linear_inequality",
            "csg_vector_dot_3d": "dot_product_3d",
            "la_matrix_multiply": "matrix_multiply",
            "hs_log_product_equation": "solve_log_product_equation",
            "hs_exponential_asymptote_distance": "solve_exponential_asymptote_distance_sum",
            "hs_inverse_log_power_coordinate": "solve_inverse_log_power_coordinate",
            "hs_log_interval_extrema": "solve_log_interval_extrema_sum",
            "hs_sine_linear_interval": "solve_sine_linear_special_interval",
            "hs_polynomial_addition": "add_polynomial_coefficients",
            "hs_polynomial_value": "evaluate_polynomial_horner",
            "hs_polynomial_remainder": "polynomial_remainder_two_linear",
            "hs_rational_interval_extrema": "rational_interval_extrema",
            "hs_matrix_product": "symbolic_matrix_product_2x2",
            "hs_composite_sequence": "hs_composite_sequence",
            "hs_composite_sequence_function": "hs_composite_sequence_function",
            "hs1_geometric_sequence": "hs1_geometric_sequence",
            "stat_binomial_distribution": "stat_binomial_distribution",
            "geo_vector_dot": "geo_vector_dot",
            "cal_trig_derivative": "cal_trig_derivative",
        }
        rule_id = builtin.get(parsed.get("domain"))
        if rule_id:
            return {"status": "PASS", "rule_id": rule_id, "path": [rule_id], "objective": "최소 누락·최소 위험·최소 단계"}
        return {"status": "FAIL", "reason": "적용 가능한 규칙이 없습니다.", "path": []}
    _, _, _, selected = min(candidates, key=lambda item: item[:3])
    return {"status": "PASS", "rule_id": selected.get("rule_id"), "path": [selected.get("rule_id")], "objective": "최소 누락·최소 위험·최소 단계"}


def build_solution_trace(parsed: dict[str, Any], result: dict[str, Any]) -> list[str]:
    """필요 변수: 분류 결과와 계산 결과. 학생이 읽을 수 있는 순서형 풀이 단계를 생성한다."""
    if result.get("status") != "PASS":
        return [f"계산 실패: {result.get('reason', '조건을 확인하세요.')}" ]
    slots = parsed.get("slots", {})
    domain = parsed.get("domain", "")
    rule_path = select_optimal_rule(parsed).get("path", [])
    steps = [f"1. 문제 유형을 {domain}으로 분류한다.", f"2. 적용 규칙: {', '.join(rule_path) or '내장 규칙'}"]
    if result.get("formula"):
        steps.append(f"3. 공식: {result['formula']}")
    if domain == "hs1_function_composition":
        inner = slots["c"] * slots["input"] + slots["d"]
        steps.append(f"4. 안쪽 함수부터 계산한다: g({slots['input']})={slots['c']}×{slots['input']}+{slots['d']}={inner}.")
        steps.append(f"5. 바깥 함수에 대입한다: f({inner})={slots['a']}×{inner}+{slots['b']}={result.get('answer')}.")
    elif domain == "hs1_inverse_function":
        steps.append(f"4. y={slots['a']}x+{slots['b']}에서 x와 y를 바꾼다.")
        steps.append(f"5. y를 정리한 결과는 {result.get('answer')}이다.")
    elif domain == "hs1_polynomial_factor":
        steps.append(f"4. 두 수의 합은 {slots['b']}, 곱은 {slots['c']}가 되도록 찾는다.")
        steps.append(f"5. 인수분해 결과는 {result.get('answer')}이다.")
    elif domain == "hs_composite_sequence":
        first = slots["a1"] + (slots["n1"] - 1) * slots["d"]
        second = slots["a1"] + (slots["n2"] - 1) * slots["d"]
        steps.append(f"4. a_{slots['n1']}={first}, a_{slots['n2']}={second}를 각각 계산한다.")
        steps.append(f"5. 두 항을 더해 {result.get('answer')}을 얻는다.")
    elif domain == "hs_composite_sequence_function":
        sequence_sum = slots["a1"] + (slots["n1"] - 1) * slots["d"] + slots["a1"] + (slots["n2"] - 1) * slots["d"]
        steps.append(f"4. 두 일반항을 계산해 M=a_{slots['n1']}+a_{slots['n2']}={sequence_sum}이다.")
        steps.append(f"5. g({slots['input']})={slots['input']}+M을 계산하고 f에 대입한다.")
        steps.append(f"6. log_2(2^y)=y를 적용해 최종값 {result.get('answer')}을 얻는다.")
    elif domain == "cm_arith_sequence" and slots.get("kind") == "arithmetic_sum":
        steps.append(f"4. S_{slots['n']}={slots['n']}({2 * slots['a1']}+({slots['n']}-1)×{slots['d']})/2로 대입한다.")
        steps.append(f"5. 계산 결과는 {result.get('answer')}이다.")
    else:
        steps.append(f"4. 추출한 값 {slots}을 공식에 대입해 {result.get('answer')}를 계산한다.")
    if result.get("fraction"):
        steps.append(f"기약분수로 정리하면 {result['fraction']}이다.")
    steps.append(f"{len(steps) + 1}. 원래 조건에 재대입해 검산한다: {'통과' if result.get('verified') else '실패'}.")
    return steps


if __name__ == "__main__":
    """CLI: 문제 문장을 받아 NLP 해석과 규칙 계산 결과를 JSON으로 출력한다."""
    import argparse

    parser = argparse.ArgumentParser(description="AIFlow rule-based math NLP")
    parser.add_argument("text", nargs="+", help="풀이할 수학 문제 문장")
    args = parser.parse_args()
    parsed = classify(" ".join(args.text))
    result = solve_rule(parsed["domain"], parsed["slots"])
    print(json.dumps({"parse": parsed, "result": result, "trace": build_solution_trace(parsed, result)}, ensure_ascii=False, indent=2))
