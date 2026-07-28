"""비공개 PDF를 OCR용 PNG 페이지로 렌더링한다.

필요 변수: pdf(입력 PDF), output_dir(비공개 출력), scale(렌더 배율).
작동 원리: PyMuPDF가 각 페이지를 독립 PNG로 만들고 SHA-256·페이지 수를
manifest에 UTF-8로 기록한다. 저작권 원문은 private_benchmarks 아래만 허용한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = (PROJECT_ROOT / "private_benchmarks").resolve()


def private_path(value: str) -> Path:
    """변수: 사용자 출력 경로. 원리: resolve 후 private_benchmarks 밖의 원문 렌더 저장을 차단한다."""
    candidate = Path(value)
    resolved = (PROJECT_ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if PRIVATE_ROOT != resolved and PRIVATE_ROOT not in resolved.parents:
        raise argparse.ArgumentTypeError("출력 경로는 private_benchmarks 하위여야 합니다.")
    return resolved


def sha256(path: Path) -> str:
    """변수: 파일 경로. 원리: 일정한 1 MiB 블록으로 읽어 원본 식별용 SHA-256을 계산한다."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    """명령행 입력 PDF를 페이지별 PNG와 매니페스트로 변환한다."""
    parser = argparse.ArgumentParser(description="비공개 시험 PDF의 OCR용 페이지 PNG를 만듭니다.")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output-dir", type=private_path, required=True)
    parser.add_argument("--scale", type=float, default=2.0)
    args = parser.parse_args()
    source = args.pdf.resolve()
    if args.scale <= 0 or not source.is_file():
        raise ValueError("존재하는 PDF와 양수 렌더 배율이 필요합니다.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with fitz.open(source) as document:
        for page_number, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(args.scale, args.scale), alpha=False)
            pixmap.save(args.output_dir / f"page-{page_number:03d}.png")
        manifest = {"source_pdf": source.name, "source_pdf_sha256": sha256(source), "page_count": len(document), "scale": args.scale}
    (args.output_dir / "render_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
