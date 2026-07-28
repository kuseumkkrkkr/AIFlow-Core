"""과목별 수학 지식 데이터베이스의 공통 계약을 검증한다."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from knowledge_catalog import REQUIRED_ITEM_FIELDS, load_tool_knowledge_catalogs  # noqa: E402
from math_tools import MATH_TOOL_REGISTRY  # noqa: E402
from rule_based_nlp import RULE_SOLVER_DOMAIN_BY_ID  # noqa: E402


def test_tool_knowledge_catalogs_are_complete() -> None:
    """과목별 지식 항목이 공통 필수 필드와 유일한 concept_id를 가지는지 확인한다."""
    catalogs = load_tool_knowledge_catalogs()
    assert {
        "math1_tool_catalog", "calculus_tool_catalog", "stats_geometry_tool_catalog",
        "advanced_algebra_tool_catalog", "advanced_calculus_tool_catalog", "advanced_stats_geometry_tool_catalog",
        "functions_inequalities_tool_catalog", "calculus_applications_tool_catalog", "combinatorics_spacegeo_tool_catalog",
        "linear_algebra_tool_catalog", "foundations_analysis_tool_catalog", "discrete_math_tool_catalog",
        "abstract_algebra_tool_catalog", "numerical_optimization_tool_catalog", "advanced_geometry_tool_catalog",
        "probability_statistics_advanced_tool_catalog", "differential_equations_tool_catalog", "complex_analysis_tool_catalog",
        "geometry_gui_tool_catalog",
    } <= set(catalogs)
    entries = [item for catalog in catalogs.values() for item in catalog["items"]]
    assert len(entries) >= 440
    assert len({item["concept_id"] for item in entries}) == len(entries)
    assert all(item.get(field) for item in entries for field in REQUIRED_ITEM_FIELDS)
    assert {item["execution_status"] for item in entries} <= {"실행 가능", "제한 실행", "도구 구현 대기"}
    assert all("_tool_catalog" not in item["subject"] for item in entries)
    assert all(isinstance(item.get("prerequisite_ids"), list) for item in entries)
    known_ids = {item["concept_id"] for item in entries}
    assert all(prerequisite in known_ids for item in entries for prerequisite in item["prerequisite_ids"])
    prerequisites = {item["concept_id"]: item["prerequisite_ids"] for item in entries}
    visiting, visited = set(), set()

    def visit(concept_id: str) -> None:
        """변수: 개념 ID와 선수 그래프. 원리: DFS 방문 상태로 자기 참조·순환 선수관계를 거부한다."""
        assert concept_id not in visiting
        if concept_id in visited:
            return
        visiting.add(concept_id)
        for prerequisite in prerequisites[concept_id]:
            visit(prerequisite)
        visiting.remove(concept_id)
        visited.add(concept_id)

    for concept_id in prerequisites:
        visit(concept_id)
    active_entries = [item for item in entries if item["execution_status"] in {"실행 가능", "제한 실행"}]
    for item in active_entries:
        tool = item["tool"]
        if isinstance(tool, dict) and tool.get("kind") == "math_tool":
            assert tool.get("id") in MATH_TOOL_REGISTRY
        else:
            tool_id = tool.get("id") if isinstance(tool, dict) else tool
            assert tool_id in RULE_SOLVER_DOMAIN_BY_ID


if __name__ == "__main__":
    test_tool_knowledge_catalogs_are_complete()
    print("PASS: knowledge catalog")
