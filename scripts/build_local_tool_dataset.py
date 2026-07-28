"""AIFlow OMJ의 문제·풀이를 읽어 로컬 도구 감지 학습셋을 만든다.

사용자·답안·채팅 테이블은 읽지 않는다. quest_data와 solve_step만 read-only로 읽고,
문제 원문은 private_benchmarks에만 저장한다. 레이블은 기존 규칙 엔진이 검산까지 통과한
도구로 제한해, 오답 또는 풀이 텍스트의 우연한 키워드가 학습 신호가 되지 않게 한다.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from solver_router import solve_with_router  # noqa: E402


def _blocks_to_text(value: str | None) -> str:
    """변수: OMJ blocks JSON 또는 문자열. 원리: text·latex 블록만 순서대로 합쳐 학습 입력의 수식 의미를 보존한다."""
    if not value:
        return ""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value.strip()
    if isinstance(parsed, dict) and isinstance(parsed.get("blocks"), list):
        return " ".join(str(block.get("content", "")).strip() for block in parsed["blocks"] if isinstance(block, dict)).strip()
    return str(parsed).strip()


def _read_quests(database: Path) -> list[dict[str, Any]]:
    """변수: OMJ quests.db 경로. 원리: 읽기 전용 SQLite 연결로 문제·풀이·태그만 묶고 개인정보 테이블은 쿼리하지 않는다."""
    connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """SELECT q.quest_id, q.quest_title, q.quest_answer, q.hash_tag, q.question_type,
                  GROUP_CONCAT(s.flow, '\n') AS flows, GROUP_CONCAT(s.answer_riddle, '\n') AS solutions
           FROM quest_data q LEFT JOIN solve_step s ON s.quest_id=q.quest_id
           GROUP BY q.quest_id"""
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def build_records(database: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """변수: 사용자 소유 OMJ 문제 DB. 원리: 규칙 엔진이 PASS·검산한 문항만 도구 라벨로 승격하고 나머지는 제외한다."""
    accepted: list[dict[str, Any]] = []
    rejected = Counter()
    for row in _read_quests(database):
        question = _blocks_to_text(row["quest_title"])
        if len(question) < 3:
            rejected["empty_question"] += 1
            continue
        result = solve_with_router(question, "rule")
        if result.get("status") != "PASS" or result.get("result", {}).get("verified") is not True:
            rejected["unsupported_or_unverified"] += 1
            continue
        domain = str(result["router"]["selected_domain"])
        tags = _blocks_to_text(row["hash_tag"])
        solution = " ".join(filter(None, (_blocks_to_text(row["flows"]), _blocks_to_text(row["solutions"])))).strip()
        accepted.append({
            "record_id": f"omj:{row['quest_id']}", "question": question,
            "tool_domain": domain, "tags": tags, "solution_context": solution,
            "label_source": "rule_verified", "source": "user_owned_omj",
        })
    counts = Counter(record["tool_domain"] for record in accepted)
    report = {"source": str(database), "accepted": len(accepted), "rejected": dict(rejected), "labels": dict(sorted(counts.items()))}
    return accepted, report


def main() -> int:
    """변수: DB·출력 경로. 원리: UTF-8 JSONL과 집계 보고서를 비공개 학습 폴더에 만들고 모델 학습의 입력 계약을 고정한다."""
    parser = argparse.ArgumentParser(description="OMJ 문제 DB에서 로컬 도구 감지 학습셋 생성")
    parser.add_argument("--database", type=Path, default=ROOT.parents[0] / "Upstudy-app-vercel" / "omj" / "quests.db")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "private_benchmarks" / "local_embedder")
    args = parser.parse_args()
    records, report = build_records(args.database)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "omj_tool_detection.jsonl").write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else ""), encoding="utf-8")
    (args.output_dir / "omj_tool_detection_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
