"""MIT 라이선스 GSM8K 평가 분할을 연구용 비공개 코퍼스로 가져온다.

문제 전문·풀이 전문은 private_benchmarks 아래에만 저장한다. 이 스크립트는
학습용 train 분할을 내려받지 않으며, 공개 모델의 수학 추론 평가에 필요한
test 1,319문항만 UTF-8 JSON으로 보관한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


ROWS_URL = "https://datasets-server.huggingface.co/rows"
DATASET_ID = "openai/gsm8k"
LICENSE = "MIT"


def _request_rows(offset: int, length: int) -> list[dict]:
    """변수: 시작 오프셋·요청 행 수. 원리: 공개 데이터셋 서버에서 GSM8K main/test 행을 UTF-8 JSON으로 읽는다."""
    query = urlencode({"dataset": DATASET_ID, "config": "main", "split": "test", "offset": offset, "length": length})
    with urlopen(f"{ROWS_URL}?{query}", timeout=30) as response:  # nosec B310: 고정된 HTTPS 공개 데이터셋 URL이다.
        payload = json.loads(response.read().decode("utf-8"))
    return [entry["row"] for entry in payload.get("rows", [])]


def _final_answer(answer: str) -> str | None:
    """변수: GSM8K 풀이 전문. 원리: 공식 표기 #### 뒤 최종 정답만 평가 정답으로 분리한다."""
    marker = "####"
    return answer.rsplit(marker, 1)[-1].strip() if marker in answer else None


def import_gsm8k(output_dir: Path, page_size: int = 100) -> dict:
    """변수: private 출력 경로·페이지 크기. 원리: 모든 test 행을 수집하고 원문 해시·라이선스 메타데이터를 함께 기록한다."""
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    offset = 0
    while True:
        rows = _request_rows(offset, page_size)
        if not rows:
            break
        for index, row in enumerate(rows, start=offset):
            question, solution = str(row["question"]), str(row["answer"])
            records.append({
                "case_id": f"gsm8k-test-{index:04d}", "question": question, "solution": solution,
                "expected": _final_answer(solution), "source": "openai/gsm8k main test", "license": LICENSE,
            })
        offset += len(rows)
        if len(rows) < page_size:
            break
    serialized = json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")
    corpus_path = output_dir / "gsm8k_main_test.json"
    corpus_path.write_bytes(serialized)
    manifest = {
        "dataset": DATASET_ID, "config": "main", "split": "test", "license": LICENSE,
        "source_url": "https://huggingface.co/datasets/openai/gsm8k", "records": len(records),
        "sha256": hashlib.sha256(serialized).hexdigest(), "storage": "private_benchmarks only",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    """변수: CLI 출력 경로·페이지 크기. 원리: 연구용 private 디렉터리로만 GSM8K 평가셋을 가져온다."""
    parser = argparse.ArgumentParser(description="GSM8K test를 private benchmark로 가져옵니다.")
    parser.add_argument("--output-dir", default="private_benchmarks/public/gsm8k_main_test")
    parser.add_argument("--page-size", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.page_size <= 100:
        raise SystemExit("--page-size는 1~100이어야 합니다.")
    print(json.dumps(import_gsm8k(Path(args.output_dir), args.page_size), ensure_ascii=False))


if __name__ == "__main__":
    main()
