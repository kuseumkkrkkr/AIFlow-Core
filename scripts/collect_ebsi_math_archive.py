"""EBSi 공개 기출 아카이브에서 수학 원문 자산을 로컬 비공개 코퍼스로 수집한다.

필요 변수: 시행 연도, 시행 월, 출력 경로, 내려받기 여부.
작동 원리: EBSi 공개 목록 AJAX가 반환하는 수학 문제 PDF와 정답 자산 URL만 읽어
SHA-256·출처·시행일·자산 종류를 manifest로 구조화한다. 저작권 원문은 반드시
private_benchmarks 아래에만 저장하며 Git·Vercel 자산으로 복사하지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = (ROOT / "private_benchmarks").resolve()
EBSI_LIST_URL = "https://www.ebsi.co.kr/ebs/xip/xipc/previousPaperListAjax.ajax"
EBSI_DOWNLOAD_ROOT = "https://wdown.ebsi.co.kr/W61001/01exam"
MATH_TRACKS = {
    "mathA": "확률과 통계",
    "mathB": "미적분",
    "mathC": "기하",
}


def _request_html(year: int, months: list[str], page: int) -> str:
    """변수: 달력 연도·시행 월·목록 쪽수. 원리: EBSi 공개 목록과 같은 폼 값을 POST로 보내 해당 페이지 HTML을 가져온다."""
    fields = [
        ("targetCd", "D300"), ("yearList", str(year)), ("monthList", ",".join(months)),
        ("arOrd", "1,2,3,4,5,,6,7,8"), ("subjIdList", "firstEnter"),
        ("sort", "recent"), ("currentPage", str(page)), ("year", str(year)),
        ("mathArOrd", "2"),
    ]
    fields.extend(("month", month) for month in months)
    fields.extend(("sFormPartMath", subject) for subject in ("140119", "140120", "140121", "mathPast"))
    request = Request(EBSI_LIST_URL, data=urlencode(fields).encode("utf-8"), headers={
        "User-Agent": "AIFlow-Core research collector/0.5",
        "Referer": "https://www.ebsi.co.kr/ebs/xip/xipc/previousPaperList.ebs?targetCd=D300",
        "X-Requested-With": "XMLHttpRequest",
    })
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _asset_rows(html: str, year: int) -> list[dict[str, str | int]]:
    """변수: EBSi 목록 HTML·시행 연도. 원리: 수학 문제 버튼과 같은 카드의 정답 버튼 URL을 짝지어 재현 가능한 자산 행으로 바꾼다."""
    rows: list[dict[str, str | int]] = []
    question_pattern = r"goDownLoadP\('(?P<path>/[^']*?/go3/math[^']+\.pdf)'"
    for question in re.finditer(question_pattern, html):
        # EBSi 목록은 li가 아닌 div 카드로 반환되므로, 문제 버튼 바로 뒤의 정답 버튼만 찾는다.
        answer = re.search(
            r"goDownLoadJ\('(?P<url>https://wdown\.ebsi\.co\.kr/[^']+)'",
            html[question.end():question.end() + 1400],
        )
        question_url = EBSI_DOWNLOAD_ROOT + question.group("path")
        source_date = re.search(r"/(\d{8})/", question_url)
        source_filename = question.group("path").rsplit("/", 1)[-1]
        track_key = next((key for key in MATH_TRACKS if source_filename.startswith(key)), "common")
        rows.append({
            "calendar_year": year,
            "session_date": source_date.group(1) if source_date else "unknown",
            "subject_track": MATH_TRACKS.get(track_key, "공통 수학"),
            "asset_kind": "question_pdf",
            "source_url": question_url,
            "source_provider": "EBSi 공개 기출 아카이브",
        })
        if answer:
            rows.append({
                "calendar_year": year,
                "session_date": source_date.group(1) if source_date else "unknown",
                "subject_track": MATH_TRACKS.get(track_key, "공통 수학"),
                "asset_kind": "answer_image",
                "source_url": answer.group("url"),
                "source_provider": "EBSi 공개 기출 아카이브",
            })
    return rows


def _build_sessions(records: list[dict[str, str | int]]) -> list[dict[str, object]]:
    """변수: 원문 자산 행. 원리: 시행일과 선택과목으로 문제·정답을 같은 회차 묶음에 연결해 학습 파서가 순회할 인덱스를 만든다."""
    grouped: dict[tuple[str, str], list[dict[str, str | int]]] = {}
    for record in records:
        key = (str(record["session_date"]), str(record["subject_track"]))
        grouped.setdefault(key, []).append(record)
    sessions: list[dict[str, object]] = []
    for (session_date, subject_track), assets in sorted(grouped.items()):
        sessions.append({
            "session_id": f"ebsi-{session_date}-{subject_track}",
            "session_date": session_date,
            "subject_track": subject_track,
            "question_assets": [asset for asset in assets if asset["asset_kind"] == "question_pdf"],
            "answer_assets": [asset for asset in assets if asset["asset_kind"] == "answer_image"],
        })
    return sessions


def _sha256_file(path: Path) -> str:
    """변수: 이미 내려받은 파일 경로. 원리: 파일을 조각 단위로 읽어 메모리를 크게 쓰지 않고 SHA-256을 재계산한다."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> str:
    """변수: 공개 원문 URL·비공개 저장 파일. 원리: 응답을 스트리밍 저장하며 SHA-256을 함께 계산하고 실패한 부분 파일은 제거한다."""
    temporary = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    request = Request(url, headers={"User-Agent": "AIFlow-Core research collector/0.5"})
    try:
        with urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return digest.hexdigest()


def _safe_destination(output_dir: Path, row: dict[str, str | int]) -> Path:
    """변수: private 출력 폴더·자산 행. 원리: URL 끝 파일명 앞에 연도와 종류를 붙여 동명 파일 충돌을 막는다."""
    filename = str(row["source_url"]).rsplit("/", 1)[-1]
    return output_dir / f"{row['calendar_year']}_{row['asset_kind']}_{filename}"


def main() -> int:
    """변수: 연도 범위·월·저장 옵션. 원리: 페이지를 끝까지 순회해 중복 URL을 제거한 뒤, 선택 시 원문과 해시를 local manifest에 기록한다."""
    parser = argparse.ArgumentParser(description="EBSi 공개 수학 기출 자산을 private 코퍼스로 수집합니다.")
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--months", default="06,09,11", help="달력 기준 시행 월 목록(쉼표 구분)")
    parser.add_argument("--output-dir", type=Path, default=PRIVATE_ROOT / "official" / "ebsi_10y_math_assets")
    parser.add_argument("--download", action="store_true", help="지정할 때만 원문을 private 경로에 내려받습니다.")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if PRIVATE_ROOT != output_dir and PRIVATE_ROOT not in output_dir.parents:
        raise ValueError("출력 경로는 private_benchmarks 하위여야 합니다.")
    months = [month.strip().zfill(2) for month in args.months.split(",") if month.strip()]
    rows: list[dict[str, str | int]] = []
    for year in range(args.start_year, args.end_year + 1):
        for page in range(1, 80):
            page_rows = _asset_rows(_request_html(year, months, page), year)
            if not page_rows:
                break
            rows.extend(page_rows)
    unique: dict[str, dict[str, str | int]] = {str(row["source_url"]): row for row in rows}
    records = list(unique.values())
    if args.download:
        output_dir.mkdir(parents=True, exist_ok=True)
        for row in records:
            destination = _safe_destination(output_dir, row)
            row["filename"] = destination.name
            row["sha256"] = _download(str(row["source_url"]), destination) if not destination.exists() else _sha256_file(destination)
    manifest = {
        "collector": "collect_ebsi_math_archive.py",
        "collected_at_utc": datetime.now(UTC).isoformat(),
        "year_range": [args.start_year, args.end_year],
        "months": months,
        "downloaded": args.download,
        "copyright_boundary": "원문 자산은 private_benchmarks에만 보관하며 Git·Vercel에 포함하지 않는다.",
        "assets": records,
    }
    if args.download:
        (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sessions = {
            "schema_version": 1,
            "source": "EBSi 공개 기출 아카이브",
            "copyright_boundary": manifest["copyright_boundary"],
            "sessions": _build_sessions(records),
        }
        (output_dir / "sessions.json").write_text(json.dumps(sessions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"assets": len(records), "downloaded": args.download, "output_dir": str(output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
