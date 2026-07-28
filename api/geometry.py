"""AIFlow-Core 좌표 평면 GUI 전용 기하 API."""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from geometry_gui import solve_geometry_payload  # noqa: E402


class handler(BaseHTTPRequestHandler):
    """필요 변수: GUI가 만든 점·연산 JSON. 작동 원리: 자연어 라우터 없이 구조화된 기하 엔진만 호출한다."""

    def _send(self, status: int, payload: dict) -> None:
        """필요 변수: HTTP 상태와 JSON payload. 작동 원리: UTF-8 JSON 응답과 브라우저 CORS 헤더를 전송한다."""
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

    def do_GET(self) -> None:  # noqa: N802
        """GUI 전용 엔드포인트의 연산 목록을 반환한다."""
        self._send(200, {"status": "ok", "input_mode": "structured-coordinate-gui", "operations": ["distance", "midpoint", "triangle_area", "vector_dot", "line_intersection"]})

    def do_POST(self) -> None:  # noqa: N802
        """필요 변수: 200KB 이하 UTF-8 JSON. 작동 원리: 점 배열을 검증하고 기하 풀이·검산 결과를 돌려준다."""
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 200_000:
                self._send(413, {"status": "FAIL", "reason": "입력 크기가 올바르지 않습니다."})
                return
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(payload, dict):
                self._send(400, {"status": "FAIL", "reason": "JSON 객체가 필요합니다."})
                return
            result = solve_geometry_payload(payload)
            self._send(200, result)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            self._send(400, {"status": "FAIL", "reason": f"입력 해석 실패: {exc}"})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"status": "FAIL", "reason": f"기하 엔진 실행 실패: {exc}"})
