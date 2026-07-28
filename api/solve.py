"""AIFlow-Core 전체 규칙 엔진을 Vercel에서 호출하는 경량 Python 함수."""
from __future__ import annotations

import json
import sys
from fractions import Fraction
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from solver_router import solve_with_router  # noqa: E402


def _json_default(value: object) -> str:
    """필요 변수: JSON 기본 인코더가 처리하지 못한 값. 작동 원리: 수학 슬롯의 Fraction을 정확한 분수 문자열로 보존한다."""
    if isinstance(value, Fraction):
        return str(value)
    raise TypeError(f"JSON으로 변환할 수 없는 값입니다: {type(value).__name__}")


class handler(BaseHTTPRequestHandler):
    """필요 변수: HTTP 요청. 작동 원리: 문제를 전체 규칙 엔진에 전달하고 JSON 결과를 반환한다."""

    def _send(self, status: int, payload: dict) -> None:
        """필요 변수: HTTP 상태와 JSON payload. 작동 원리: UTF-8 JSON 응답을 만든다."""
        body = json.dumps(payload, ensure_ascii=False, default=_json_default).encode("utf-8")
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
        """간단한 엔진 상태를 반환한다."""
        self._send(200, {"status": "ok", "engine": "AIFlow-Core v0.5"})

    def do_POST(self) -> None:  # noqa: N802
        """필요 변수: question 문자열. 작동 원리: 분류→규칙 선택→풀이 trace→검산을 실행한다."""
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 200_000:
                self._send(413, {"status": "FAIL", "reason": "입력 크기가 올바르지 않습니다."})
                return
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            question = str(payload.get("question", "")).strip()
            if not question:
                self._send(400, {"status": "FAIL", "reason": "question이 비어 있습니다."})
                return
            mode = str(payload.get("router", "rule"))
            response = solve_with_router(question, mode)
            response["summary"] = (
                f"{response['router'].get('selected_domain')} 도구 경로로 정답 {response['result'].get('answer')}를 계산하고 재검산했습니다."
                if response.get("status") == "PASS"
                else str(response.get("reason", "문제를 해석하지 못했습니다."))
            )
            self._send(200, response)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send(400, {"status": "FAIL", "reason": f"입력 해석 실패: {exc}"})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"status": "FAIL", "reason": f"엔진 실행 실패: {exc}"})
