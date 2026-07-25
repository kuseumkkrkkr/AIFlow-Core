"""문제 생성 파라미터를 받아 생성·정답·풀이·검산 루프를 실행하는 Vercel 함수."""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from problem_generation_loop import GenerationConfig, generate_and_validate  # noqa: E402


class handler(BaseHTTPRequestHandler):
    """필요 변수: 생성 설정 JSON. 작동 원리: 제한된 파라미터로 재현 가능한 생성 루프를 실행한다."""

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
        """필요 변수: min_grade·max_grade·repeats·seed·include_mock. 결과를 요약과 문항 목록으로 반환한다."""
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 30_000:
                self._send(413, {"status": "FAIL", "reason": "생성 요청 크기가 올바르지 않습니다."})
                return
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            repeats = min(max(int(payload.get("repeats", 1)), 1), 20)
            seed = int(payload.get("seed", 2026))
            config = GenerationConfig(
                min_grade=str(payload.get("min_grade", "중3")),
                max_grade=str(payload.get("max_grade", "고2")),
                repeats=repeats,
                seed=seed,
                include_mock=bool(payload.get("include_mock", True)),
            )
            if config.min_grade not in {"중3", "고1", "수1", "수2", "고2"} or config.max_grade not in {"중3", "고1", "수1", "수2", "고2"}:
                self._send(400, {"status": "FAIL", "reason": "학년은 중3·고1·수1·수2·고2 중 하나여야 합니다."})
                return
            report = generate_and_validate(config)
            self._send(200, {"status": "PASS" if report["failed"] == 0 else "FAIL", "summary": {key: report[key] for key in ("config", "total", "passed", "failed", "pass_rate")}, "cases": report["cases"]})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send(400, {"status": "FAIL", "reason": f"생성 파라미터 해석 실패: {exc}"})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"status": "FAIL", "reason": f"생성 루프 실행 실패: {exc}"})
