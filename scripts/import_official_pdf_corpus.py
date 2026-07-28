"""공식 공개 문제지·정답표를 비공개 로컬 코퍼스로 내려받는 도구.

필요 변수: exam_id, question_url, answer_url, output_dir.
작동 원리: 각 URL을 UTF-8 메타데이터와 함께 ``private_benchmarks`` 아래에
저장하고 SHA-256을 계산한다. 원문 PDF는 저작권·재배포 경계를 지키기 위해
Git 추적 경로에 쓰지 않는다. 이 도구는 원문을 파싱하거나 공개하지 않는다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = (PROJECT_ROOT / "private_benchmarks").resolve()


def _download(url: str, destination: Path) -> str:
    """URL의 PDF를 내려받고 SHA-256을 반환한다.

    변수: url은 공식 원본 주소, destination은 비공개 로컬 저장 위치다.
    원리: 네트워크 응답을 조각 단위로 쓰면서 동시에 해시하므로 대용량 PDF를
    메모리에 전부 올리지 않는다. 실패한 파일은 남기지 않아 다음 실행이 안전하다.
    """

    digest = hashlib.sha256()
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = Request(url, headers={"User-Agent": "AIFlow-Core research importer/0.5"})

    try:
        with urlopen(request, timeout=30) as response, temporary.open("wb") as output:
            content_type = response.headers.get_content_type()
            if content_type not in {"application/pdf", "application/octet-stream"}:
                raise ValueError(f"PDF가 아닌 응답입니다: {content_type}")
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    return digest.hexdigest()


def _private_output_dir(value: str) -> Path:
    """출력 경로가 비공개 코퍼스 루트 안인지 확인한다.

    변수: value는 사용자가 전달한 상대 또는 절대 경로다.
    원리: 원문 기출이 공개 저장소나 배포 디렉터리에 기록되지 않도록 resolve 후
    ``private_benchmarks`` 하위인지 검사한다.
    """

    candidate = Path(value)
    resolved = (PROJECT_ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if PRIVATE_ROOT != resolved and PRIVATE_ROOT not in resolved.parents:
        raise argparse.ArgumentTypeError("출력 경로는 private_benchmarks 하위여야 합니다.")
    return resolved


def main() -> None:
    """명령행 인자를 읽어 문제지·정답표와 재현용 메타데이터를 저장한다.

    변수: exam_id는 검증 보고서에서 사용할 시험 식별자다.
    원리: 두 원본의 URL·파일명·해시·수집 시각만 manifest.json에 기록한다.
    문제 전문과 정답 전문은 PDF 내부에만 남고 Git에는 추가되지 않는다.
    """

    parser = argparse.ArgumentParser(description="공식 PDF를 비공개 검증 코퍼스로 수집합니다.")
    parser.add_argument("--exam-id", required=True)
    parser.add_argument("--question-url", required=True)
    parser.add_argument("--answer-url", required=True)
    parser.add_argument("--output-dir", required=True, type=_private_output_dir)
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    downloads = (("question", args.question_url), ("answer", args.answer_url))
    records: list[dict[str, str]] = []

    for kind, url in downloads:
        parsed = urlparse(url)
        filename = Path(parsed.path).name
        if not filename.lower().endswith(".pdf"):
            raise ValueError(f"PDF URL이 아닙니다: {url}")
        path = output_dir / filename
        records.append({"kind": kind, "source_url": url, "filename": filename, "sha256": _download(url, path)})

    manifest = {
        "exam_id": args.exam_id,
        "downloaded_at_utc": datetime.now(UTC).isoformat(),
        "copyright_boundary": "원문 PDF는 로컬 private_benchmarks에만 보관하며 Git·배포에 포함하지 않는다.",
        "files": records,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"exam_id": args.exam_id, "files": len(records), "output_dir": str(output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
