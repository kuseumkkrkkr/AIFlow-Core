"""과목별 수학 지식 카탈로그를 공통 계약으로 정규화하는 읽기 전용 로더."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


KNOWLEDGE_ROOT = Path(__file__).resolve().parents[1] / "knowledge"
REQUIRED_ITEM_FIELDS = (
    "concept_id", "name", "input_slots", "tool", "formula",
    "verification_invariant", "supported_example", "unsupported_boundary", "execution_status",
)
CATALOG_SUBJECT_DEFAULTS = {
    "math1_tool_catalog": "수학Ⅰ",
    "calculus_tool_catalog": "수학Ⅱ·미적분",
    "stats_geometry_tool_catalog": "확률과 통계·기하",
    "advanced_algebra_tool_catalog": "고2 대수·다항식·행렬",
    "advanced_calculus_tool_catalog": "고2 수열·극한·미적분",
    "advanced_stats_geometry_tool_catalog": "고2 확률분포·좌표기하·벡터",
    "linear_algebra_tool_catalog": "대학 기초수학·선형대수",
    "foundations_analysis_tool_catalog": "대학 기초수학·해석",
    "discrete_math_tool_catalog": "대학 기초수학·이산수학",
    "abstract_algebra_tool_catalog": "대학 기초수학·정수론·추상대수",
    "numerical_optimization_tool_catalog": "대학 기초수학·수치해석·최적화",
    "advanced_geometry_tool_catalog": "대학 기초수학·고급기하",
}
STATUS_ALIASES = {
    "실행 가능": "실행 가능",
    "제한 실행": "제한 실행",
    "계획됨": "도구 구현 대기",
    "도구 구현 대기": "도구 구현 대기",
    "카탈로그만 등록": "도구 구현 대기",
}


def _raw_items(document: dict[str, Any]) -> list[dict[str, Any]]:
    """변수: UTF-8 JSON 문서. 원리: 과거 카탈로그의 items/concepts 차이를 한 읽기 경로로 흡수한다."""
    items = document.get("items", document.get("concepts", []))
    return items if isinstance(items, list) else []


def _normalize_item(item: dict[str, Any], catalog_name: str) -> dict[str, Any]:
    """변수: 원본 지식 항목과 카탈로그명. 원리: 이름·검산 필드의 표기 차이를 공통 스키마로 변환한다."""
    invariant = item.get("verification_invariant", item.get("verification_invariants"))
    status = STATUS_ALIASES.get(str(item.get("execution_status", "도구 구현 대기")), "도구 구현 대기")
    return {
        "catalog": catalog_name,
        "concept_id": item.get("concept_id"),
        "name": item.get("name", item.get("name_kr")),
        "subject": item.get("subject", CATALOG_SUBJECT_DEFAULTS.get(catalog_name, catalog_name)),
        "prerequisite_ids": item.get("prerequisite_ids", []),
        "input_slots": item.get("input_slots", []),
        "tool": item.get("tool"),
        "formula": item.get("formula"),
        "verification_invariant": invariant,
        "supported_example": item.get("supported_example"),
        "unsupported_boundary": item.get("unsupported_boundary"),
        "execution_status": status,
    }


def load_tool_knowledge_catalogs() -> dict[str, dict[str, Any]]:
    """변수: knowledge/*_tool_catalog.json. 원리: 모든 과목 카탈로그를 UTF-8로 읽고 항목 스키마를 통일한다."""
    catalogs: dict[str, dict[str, Any]] = {}
    for path in sorted(KNOWLEDGE_ROOT.glob("*_tool_catalog.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        entries = [_normalize_item(item, path.stem) for item in _raw_items(document)]
        ids = [item["concept_id"] for item in entries]
        if any(not item.get(field) for item in entries for field in REQUIRED_ITEM_FIELDS) or len(ids) != len(set(ids)):
            raise ValueError(f"지식 카탈로그 계약이 올바르지 않습니다: {path.name}")
        catalogs[path.stem] = {"version": document.get("version"), "scope": document.get("scope"), "items": entries}
    return catalogs
