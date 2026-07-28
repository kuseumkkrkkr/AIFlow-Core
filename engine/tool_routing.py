"""동일한 수학 도구 후보를 세 방식으로 정렬하는 경량 라우팅 실험 모듈.

도구 실행·슬롯 추출·검산은 rule_based_nlp가 공통으로 담당한다. 이 모듈은
후보 domain의 순서만 결정하므로 실험 결과를 라우팅 차이로 비교할 수 있다.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any


@dataclass(frozen=True)
class RouteSpec:
    """변수: domain·설명·키워드. 원리: 실행 가능한 기존 solver의 검색 계약을 불변 데이터로 보관한다."""
    domain: str
    description: str
    keywords: tuple[str, ...]


ROUTE_SPECS = (
    RouteSpec("cm_linear", "일차방정식의 미지수 계산", ("일차방정식", "x를 구", "x+", "x-", "=0")),
    RouteSpec("cm_quadratic", "이차방정식과 정수근", ("이차방정식", "판별식", "x²", "x^2")),
    RouteSpec("cm_set", "집합의 합집합 교집합 원소수", ("합집합", "교집합", "|a|", "|b|", "∩", "∪")),
    RouteSpec("cm_ratio", "비례식과 비율", ("비례", "비율", ":")),
    RouteSpec("cm_probability", "조합 순열 기본 확률", ("확률", "조합", "순열", "경우의 수", "%")),
    RouteSpec("cm_geometry", "피타고라스와 기본 도형 넓이", ("피타고라스", "직각삼각형", "삼각형", "원의 넓이", "직사각형", "반지름")),
    RouteSpec("hs_cosine_law_side", "코사인 법칙으로 삼각형 변 계산", ("삼각형", "cos", "cosine", "ab=", "bc=")),
    RouteSpec("cm_arith_sequence", "등차수열 일반항과 합", ("등차수열", "첫항", "공차", "수열의 합")),
    RouteSpec("hs1_geometric_sequence", "등비수열 일반항과 합", ("등비수열", "공비")),
    RouteSpec("hs1_function_basic", "일차함수 함숫값", ("함수", "함숫값", "f(x)=")),
    RouteSpec("hs1_function_composition", "합성함수", ("합성함수", "f(g(", "g(f(")),
    RouteSpec("hs1_inverse_function", "역함수", ("역함수", "f⁻¹", "f^-1")),
    RouteSpec("hs1_polynomial_factor", "이차식 인수분해", ("인수분해", "인수정리", "다항식")),
    RouteSpec("hs_polynomial_value", "다항식 함숫값 Horner 계산", ("p(x)=", "p(", "다항식의 값", "함숫값")),
    RouteSpec("hs_polynomial_addition", "두 다항식의 동류항 계수 덧셈", ("두 다항식", "a+b", "a=", "b=")),
    RouteSpec("integer_gcd", "정수 최대공약수 유클리드 호제법", ("최대공약수", "gcd(")),
    RouteSpec("hs_absolute_linear_equation", "일차식 절댓값 방정식의 두 분기 해", ("절댓값", "절대값", "|", "=", "x")),
    RouteSpec("fn_linear_inequality", "일차부등식의 해집합과 부등호 방향", ("부등식", "≤", "≥", "<=", ">=", "<", ">", "x")),
    RouteSpec("csg_vector_dot_3d", "3차원 공간벡터 성분 내적", ("공간벡터", "3차원", "내적", "·")),
    RouteSpec("la_matrix_multiply", "명시적 정수 행렬의 행렬곱", ("행렬곱", "행렬의 곱", "a=", "b=")),
    RouteSpec("hs_log_product_equation", "두 로그의 곱 방정식", ("log_", "로그", "×", "*")),
    RouteSpec("hs_exponential_asymptote_distance", "지수함수 수평 점근선과 점 사이 거리", ("점근선", "거리", "a+b", "2^x")),
    RouteSpec("hs_inverse_log_power_coordinate", "로그함수 역함수 위 거듭제곱 좌표", ("역함수", "log_", "^k", "점")),
    RouteSpec("hs_log_interval_extrema", "로그함수 닫힌 구간 최댓값 최솟값의 합", ("최댓값", "최솟값", "log_", "x-", "x+")),
    RouteSpec("hs_sine_linear_interval", "특수각 사인 일차방정식의 라디안 구간해", ("sin", "sqrt", "방정식", "pi/", "π/")),
    RouteSpec("hs_polynomial_remainder", "두 일차식 나머지 조건 보간", ("나눈 나머지", "r(x)", "나머지를")),
    RouteSpec("hs1_exponential_log", "지수와 로그 값 계산", ("지수", "로그", "log_", "log ", "^")),
    RouteSpec("hs1_exponential_equation", "지수방정식과 로그방정식", ("지수방정식", "로그방정식", "^x=", "log_")),
    RouteSpec("hs1_trigonometry", "특수각 삼각함수", ("삼각함수", "sin", "cos", "tan", "사인", "코사인")),
    RouteSpec("hs2_limit", "다항식 극한", ("극한", "lim", "->")),
    RouteSpec("hs2_derivative", "다항식 함수 미분", ("미분", "도함수", "f'(x)", "f'(")),
    RouteSpec("hs2_tangent", "접선 기울기", ("접선", "접선의 기울기")),
    RouteSpec("hs2_integral", "거듭제곱 정적분", ("정적분", "적분", "부터")),
    RouteSpec("hs2_motion_meeting", "속도함수 적분으로 같은 위치 시각", ("속도", "위치", "원점", "출발", "v1(t)=", "v2(t)=")),
    RouteSpec("hs_rational_interval_extrema", "유리함수 구간 최댓값 최솟값", ("최댓값", "최솟값", "a/(x-", "a/(x -")),
    RouteSpec("hs_matrix_product", "양의 정수 미지수 2x2 행렬 곱", ("두 행렬", "행렬 a", "행렬 b", "ab=")),
    RouteSpec("hs1_conditional_probability", "조건부확률", ("조건부확률", "p(a|b)", "p(a∩b)")),
    RouteSpec("stat_binomial_distribution", "이항분포 점확률", ("이항분포", "n=", "p=")),
    RouteSpec("geo_vector_dot", "평면벡터 내적", ("벡터 내적", "내적", "·")),
    RouteSpec("cal_trig_derivative", "삼각함수 도함수", ("sin x의 도함수", "cos x의 도함수", "삼각함수 미분")),
    RouteSpec("hs_composite_sequence", "등차수열 결합 항 계산", ("복합중", "a5+a8")),
    RouteSpec("hs_composite_sequence_function", "수열과 합성함수 결합", ("복합상", "m=a", "log_2(2^")),
)


def _tokens(text: str) -> set[str]:
    """변수: 정규화 문제. 원리: 한글 어절·영숫자·기호를 함께 보존해 수식 키워드 검색에 쓴다."""
    import re
    return set(re.findall(r"[가-힣a-z0-9_²^+\-*/|∩∪]+", text.lower()))


def _ngrams(text: str, width: int = 3) -> set[str]:
    """변수: 문제 문자열. 원리: 형태 변화에 강한 고정 길이 문자 n-gram을 만든다."""
    compact = "".join(text.lower().split())
    return {compact[index:index + width] for index in range(max(0, len(compact) - width + 1))}


def _rule_score(text: str, spec: RouteSpec) -> float:
    """변수: 문제와 후보 도구. 원리: 키워드·형태 일치 수와 슬롯성 기호를 합산하는 결정론 기준선 점수다."""
    lowered = text.lower()
    hits = sum(1 for keyword in spec.keywords if keyword.lower() in lowered)
    token_overlap = len(_tokens(lowered) & _tokens(spec.description + " " + " ".join(spec.keywords)))
    structure_bonus = 0.0
    import re
    if spec.domain == "cm_linear" and re.search(r"[+-]?\d+\s*x\s*[+-]\s*\d+\s*=", lowered):
        structure_bonus = 14.0
    elif spec.domain == "cm_quadratic" and re.search(r"x\s*(?:\^\s*2|²)", lowered):
        structure_bonus = 8.0
    elif spec.domain == "hs_cosine_law_side" and re.search(r"ab\s*=\s*\d+.*?bc\s*=\s*\d+.*?cos\s*a\s*=", lowered):
        structure_bonus = 18.0
    elif spec.domain == "hs1_exponential_equation" and re.search(r"\d+\s*\^\s*\(?\s*[+-]?\s*\d*\s*x", lowered):
        structure_bonus = 16.0
    elif spec.domain == "hs1_exponential_log" and re.search(r"\d+\s*\^\s*\d+|log\s*_?\s*\d+", lowered):
        structure_bonus = 12.0
    elif spec.domain == "hs2_limit" and "lim" in lowered and "->" in lowered:
        structure_bonus = 14.0
    elif spec.domain == "hs2_derivative" and re.search(r"f\s*'\s*\(\s*[+-]?\d+\s*\)", lowered):
        structure_bonus = 16.0
    elif spec.domain == "hs2_integral" and "정적분" in lowered:
        structure_bonus = 12.0
    elif spec.domain == "hs2_motion_meeting" and re.search(r"v_?1\s*\(t\)\s*=.*?t\s*\^\s*2.*?v_?2\s*\(t\)\s*=", lowered):
        structure_bonus = 18.0
    elif spec.domain == "fn_linear_inequality" and re.search(r"[+-]?\d*\s*x\s*(?:[+-]\s*\d+)?\s*(?:<=|>=|<|>|≤|≥)\s*[+-]?\d+", lowered):
        structure_bonus = 16.0
    elif spec.domain == "csg_vector_dot_3d" and re.search(r"\([^()]+,[^()]+,[^()]+\)\s*[·.*]\s*\([^()]+,[^()]+,[^()]+\)", lowered):
        structure_bonus = 16.0
    elif spec.domain == "la_matrix_multiply" and "a=" in lowered and "b=" in lowered and "ab=" not in lowered:
        structure_bonus = 16.0
    return hits * 10.0 + token_overlap + structure_bonus


def _embedding_score(text: str, spec: RouteSpec) -> float:
    """변수: 문제와 후보 설명. 원리: 로컬 모델이 없을 때 재현 가능한 문자 n-gram 기준선으로만 의미 유사도를 근사한다."""
    left, right = _ngrams(text), _ngrams(spec.description + " " + " ".join(spec.keywords))
    semantic = len(left & right) / sqrt(len(left) * len(right)) if left and right else 0.0
    # 숫자뿐인 수식은 문자 n-gram만으로 도구 설명과 만날 수 없으므로, 수식 구조
    # 신호를 작은 보조 임베딩 차원으로 결합한다. 이는 후보 순서만 보정한다.
    structure = min(0.22, _rule_score(text, spec) / 120.0)
    return semantic + structure


def _neural_score(text: str, spec: RouteSpec) -> float:
    """변수: 문제·후보. 원리: 경량 내부 신경망의 프로파일 가중치(문자 임베딩 유사도+활성화)를 적용한다."""
    from mini_neural_router import neural_probabilities
    # 저장된 MLP 확률에 수식 구조 보조 신호를 더해, 숫자뿐인 입력도 후보를 잃지 않게 한다.
    return neural_probabilities(text).get(spec.domain, 0.0) + min(0.2, _rule_score(text, spec) / 120.0)


def rank_tools(text: str, mode: str = "rule", limit: int = 5) -> list[dict[str, Any]]:
    """변수: 정규화 문제·라우터 방식. 원리: 동일 후보 집합을 세 점수 함수 중 하나로 정렬해 실행 순서를 반환한다."""
    scorers = {"rule": _rule_score, "neural": _neural_score, "embedding": _embedding_score}
    if mode not in scorers:
        raise ValueError("routing mode는 rule, neural, embedding 중 하나여야 합니다.")
    # 실험 3은 로컬 체크포인트가 있는 개발 환경에서는 실제 E5 중심 벡터를 쓰고,
    # 배포 기본 경로에서는 의존성 없는 기준선을 유지한다.
    local_scores: dict[str, float] | None = None
    if mode == "embedding":
        from local_embedder_router import local_embedding_scores
        local_scores = local_embedding_scores(text)
    def score(spec: RouteSpec) -> float:
        """변수: 후보 도구 계약. 원리: 학습된 도메인은 E5 유사도를 우선하고, 미학습 도구는 구조 기준선으로 후보 집합에서 탈락하지 않게 한다."""
        # 실제 임베딩 경로의 보조 신호는 semantic n-gram이 아니라 규칙 구조 점수다.
        # 그래야 학습 데이터에 없는 도구도 명시 수식 구조로 후보에 남는다.
        baseline = _rule_score(text, spec) if local_scores is not None else scorers[mode](text, spec)
        if local_scores is None:
            return baseline
        learned = local_scores.get(spec.domain)
        if learned is not None:
            # 임베딩 유사도가 주 신호이고, 수식 구조는 동점·가까운 후보만 보정한다.
            return learned + min(0.35, baseline / 100.0)
        # 현재 OMJ 검증 레이블이 없는 실행 도구도 동일한 후보 집합에 남긴다.
        return min(0.70, baseline / 45.0)

    scored = [{"domain": spec.domain, "score": round(score(spec), 6), "description": spec.description} for spec in ROUTE_SPECS]
    return sorted(scored, key=lambda item: (-item["score"], item["domain"]))[:max(1, limit)]


def has_minimum_evidence(text: str, domain: str) -> bool:
    """변수: 정규화 문제·후보 도메인. 원리: 숫자 우연 일치만으로 다른 규칙이 PASS가 되는 허위 성공을 차단한다."""
    lowered = text.lower()
    if domain == "la_matrix_multiply":
        return "a=" in lowered and "b=" in lowered and "ab=" not in lowered
    # |ax+b|=c는 일반 일차방정식으로 괄호를 무시해 풀면 두 해 중 하나를 허위 PASS할 수 있다.
    if domain == "cm_linear" and ("|" in lowered or any(marker in lowered for marker in ("<=", ">=", "≤", "≥", "<", ">"))):
        return False
    strict_markers = {
        "cm_probability": ("확률", "조합", "순열", "경우의 수", "%"),
        "cm_geometry": ("피타고라스", "직각삼각형", "삼각형", "원의", "직사각형", "반지름"),
        "hs1_function_composition": ("합성함수", "f(g(", "g(f("),
        "hs1_inverse_function": ("역함수", "f⁻¹", "f^-1"),
        "hs_composite_sequence": ("복합중",),
        "hs_composite_sequence_function": ("복합상",),
        "hs_matrix_product": ("두 행렬", "ab="),
        "hs_polynomial_value": ("p(x)=", "p(x) ="),
        "hs_polynomial_addition": ("a+b", "두 다항식"),
        "integer_gcd": ("최대공약수", "gcd("),
        "hs_absolute_linear_equation": ("절댓값", "절대값", "|"),
        "fn_linear_inequality": ("부등식", "≤", "≥", "<=", ">=", "<", ">"),
        "csg_vector_dot_3d": ("공간벡터", "3차원", "내적", "·"),
        "hs_log_product_equation": ("log_",),
        "hs_exponential_asymptote_distance": ("점근선", "거리"),
        "hs_inverse_log_power_coordinate": ("역함수", "log_", "^k"),
        "hs_log_interval_extrema": ("최댓값", "최솟값", "log_"),
        "hs_sine_linear_interval": ("sin", "sqrt"),
        "hs2_integral": ("정적분", "부정적분", "적분"),
        "hs2_motion_meeting": ("속도", "위치", "원점", "출발"),
        "hs_rational_interval_extrema": ("최댓값", "최솟값"),
    }
    markers = strict_markers.get(domain)
    return any(marker in lowered for marker in markers) if markers else True
