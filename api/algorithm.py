"""AIFlow-Core 전체 풀이·생성 알고리즘을 공개하는 읽기 전용 Vercel 함수."""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from knowledge_catalog import load_tool_knowledge_catalogs  # noqa: E402
from mini_neural_router import MODEL_VERSION  # noqa: E402
from math_tools import MATH_TOOL_REGISTRY  # noqa: E402
from problem_generation_loop import DIFFICULTY_POLICY, FORMULA_KNOWLEDGE  # noqa: E402
from solver_router import ROUTER_VERSIONS  # noqa: E402


def _load_curriculum_catalog() -> dict:
    """필요 변수: 지식 카탈로그 UTF-8 경로. 작동 원리: 웹 명세와 엔진이 같은 과목 지식 목록을 사용한다."""
    catalog_path = ROOT / "knowledge" / "high_school_curriculum_catalog.json"
    return json.loads(catalog_path.read_text(encoding="utf-8"))


ALGORITHM = {
    "version": "AIFlow-Core v0.5",
    "pipeline": [
        {"step": 1, "name": "LaTeX·문자 정규화", "detail": "고교 핵심 LaTeX, NFKC와 유니코드 숫자를 통일하고 미지원 명령은 FAIL로 표시한다."},
        {"step": 2, "name": "도구 후보 검색", "detail": "rule·mini neural·local embedding 중 선택한 라우터가 같은 도구 후보의 순서를 정한다."},
        {"step": 3, "name": "슬롯 추출", "detail": "계수·입력값·범위·조건을 구조화한다."},
        {"step": 4, "name": "규칙 경로 선택", "detail": "필수 슬롯 누락·위험도·단계 수가 가장 작은 지식 규칙을 선택한다."},
        {"step": 5, "name": "수학 도구 호출", "detail": "구조화된 슬롯만 허용 목록의 계산 도구로 전달하고, 도구 결과를 trace에 기록한다."},
        {"step": 6, "name": "독립 검산", "detail": "결과를 원래 조건에 재대입하고 불충분하면 임의 답 대신 FAIL을 반환한다."},
    ],
    "generation_difficulty": {
        "policy": {"하": DIFFICULTY_POLICY["하"], "중": DIFFICULTY_POLICY["중"], "상": DIFFICULTY_POLICY["상"]},
        "tuple_definition": ["최소 공식 수", "최대 공식 수", "동일 공식 최대 중복"],
        "formula_knowledge": list(FORMULA_KNOWLEDGE),
    },
    "math_tools": sorted(MATH_TOOL_REGISTRY),
    "geometry_gui": {
        "input_mode": "structured-coordinate-gui",
        "principle": "WolframAlpha식 자연어 도형 질의 대신, 사용자가 좌표 평면에서 만든 점·선택 순서를 JSON으로 보낸다.",
        "operations": ["distance", "midpoint", "triangle_area", "vector_dot", "line_intersection"],
        "verification": "거리 제곱식·중점 복원식·신발끈 넓이·내적 성분식·두 직선 재대입을 각각 독립 검산한다.",
    },
    "routing_experiments": {
        "modes": ROUTER_VERSIONS,
        "neural_model": MODEL_VERSION,
        "embedding": "local-char-ngram-embedding-v1",
        "comparison_contract": "후보 집합·슬롯 추출·계산·검산·시간 제한을 공유하고 도구 순서만 비교한다.",
        "private_report_contract": {
            "corpus_storage": "private_benchmarks/ (Git·Vercel 제외)",
            "repeats": 2,
            "metrics": ["tool_selection_accuracy", "answer_accuracy", "verification_pass_rate", "false_pass_rate", "unsupported_rejection_accuracy", "deterministic_pass_rate", "mean_elapsed_ms"],
            "grouping": "curriculum",
        },
    },
    # 카탈로그는 검색·확장 우선순위를 위한 지식 목록이며, 모든 항목이 아직 실행 규칙이라는 뜻은 아니다.
    "curriculum_knowledge": _load_curriculum_catalog(),
    "tool_knowledge_catalogs": load_tool_knowledge_catalogs(),
    "supported_domains": [
        "중3: 일차·이차방정식, 비율, 집합, 확률, 도형, 등차수열",
        "고1·수1: 함수, 합성·역함수, 인수분해, 지수·로그, 삼각함수",
        "수2: 극한, 미분, 접선, 적분",
        "도구 호출: 두 일차식 나머지 보간, 유리함수 구간 극값, 2×2 행렬 곱",
    ],
}


class handler(BaseHTTPRequestHandler):
    """필요 변수: 없음. 알고리즘 설명을 UTF-8 JSON으로 반환한다."""

    def do_GET(self) -> None:  # noqa: N802
        """읽기 전용 알고리즘 명세를 공개한다."""
        body = json.dumps(ALGORITHM, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
