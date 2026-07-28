"""과목별 수학 지식 데이터베이스의 공통 계약을 검증한다."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from knowledge_catalog import REQUIRED_ITEM_FIELDS, load_tool_knowledge_catalogs  # noqa: E402


def test_tool_knowledge_catalogs_are_complete() -> None:
    """과목별 지식 항목이 공통 필수 필드와 유일한 concept_id를 가지는지 확인한다."""
    catalogs = load_tool_knowledge_catalogs()
    assert set(catalogs) == {"math1_tool_catalog", "calculus_tool_catalog", "stats_geometry_tool_catalog"}
    entries = [item for catalog in catalogs.values() for item in catalog["items"]]
    assert len(entries) >= 39
    assert len({item["concept_id"] for item in entries}) == len(entries)
    assert all(item.get(field) for item in entries for field in REQUIRED_ITEM_FIELDS)


if __name__ == "__main__":
    test_tool_knowledge_catalogs_are_complete()
    print("PASS: knowledge catalog")
