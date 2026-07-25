"""JSON 문제 배열을 받아 온라인 코퍼스 검증을 수행하는 Vercel 함수."""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from corpus_runner import evaluate_records  # noqa: E402


class handler(BaseHTTPRequestHandler):
    """필요 변수: cases 배열. 작동 원리: 사용자 문제를 전체 엔진으로 채점하고 풀이 trace를 반환한다."""

    def _send(self, status: int, payload: dict) -> None:
        """UTF-8 JSON 응답을 반환한다."""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        """브라우저 사전 요청을 허용한다."""
        self._send(204, {})

    def do_POST(self) -> None:  # noqa: N802
        """필요 변수: 최대 100개 문제 레코드. 작동 원리: 입력을 제한하고 일괄 검증한다."""
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 100_000:
                self._send(413, {"status": "FAIL", "reason": "코퍼스 크기가 올바르지 않습니다."})
                return
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            records = payload.get("cases", payload) if isinstance(payload, dict) else payload
            if not isinstance(records, list) or not records or len(records) > 100:
                self._send(400, {"status": "FAIL", "reason": "cases는 1~100개 레코드 배열이어야 합니다."})
                return
            if any(not isinstance(item, dict) or not str(item.get("question", "")).strip() for item in records):
                self._send(400, {"status": "FAIL", "reason": "각 레코드에 question이 필요합니다."})
                return
            report = evaluate_records(records, "inline-api")
            self._send(200, {"status": "PASS" if report["failed"] == 0 else "FAIL", **report})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send(400, {"status": "FAIL", "reason": f"코퍼스 입력 해석 실패: {exc}"})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"status": "FAIL", "reason": f"코퍼스 실행 실패: {exc}"})
