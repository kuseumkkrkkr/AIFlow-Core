"""AIFlow-Core 입력 수식의 제한적 LaTeX 정규화 모듈.

이 모듈은 렌더링 엔진이 아니라, 구현된 수학 도구에 전달할 수 있는 고교 핵심
LaTeX 표기를 결정론적으로 평문 기호로 바꾼다. 지원하지 않는 환경은 조용히
추측하지 않고 unsupported 목록으로 돌려보낸다.
"""
from __future__ import annotations

import re
from typing import Any


_COMMAND_REPLACEMENTS = {
    r"\\left": "", r"\\right": "", r"\\cdot": "*", r"\\times": "*",
    r"\\pi": "pi", r"\\sin": "sin", r"\\cos": "cos", r"\\tan": "tan",
    r"\\log": "log", r"\\to": "->", r"\\rightarrow": "->",
    r"\\infty": "infinity", r"\\geq": ">=", r"\\leq": "<=",
    r"\\ge": ">=", r"\\le": "<=", r"\\neq": "!=", r"\\in": "in ",
    r"\\cup": "∪", r"\\cap": "∩", r"\\sum": "sum ",
}


def _unwrap_braces(text: str) -> str:
    """변수: LaTeX 조각. 원리: 단순 지수·첨자의 중괄호를 계산 파서가 읽을 표기로 평탄화한다."""
    previous = None
    while previous != text:
        previous = text
        def convert(match: re.Match[str]) -> str:
            marker, content = match.group(1), match.group(2)
            return f"{marker}({content})" if marker == "^" and re.search(r"[+\-*/ ]", content) else f"{marker}{content}"
        text = re.sub(r"([_^])\{([^{}]+)\}", convert, text)
    return text


def _replace_fraction(text: str) -> str:
    """변수: LaTeX 문자열. 원리: 중첩되지 않은 분자·분모부터 (분자)/(분모)로 반복 치환한다."""
    pattern = re.compile(r"\\frac\{([^{}]*)\}\{([^{}]*)\}")

    def convert(match: re.Match[str]) -> str:
        numerator, denominator = match.group(1).strip(), match.group(2).strip()
        # 숫자·단일 기호 분수는 기존 슬롯 정규식이 읽는 a/b를 보존한다.
        if re.fullmatch(r"[+-]?[A-Za-z0-9.]+", numerator) and re.fullmatch(r"[+-]?[A-Za-z0-9.]+", denominator):
            return f"{numerator}/{denominator}"
        return f"({numerator})/({denominator})"
    previous = None
    while previous != text:
        previous = text
        text = pattern.sub(convert, text)
    return text


def _replace_matrix(text: str) -> str:
    """변수: LaTeX 행렬. 원리: pmatrix/bmatrix 2차원 행을 기존 2×2 슬롯 파서와 호환되는 괄호 행렬로 바꾼다."""
    pattern = re.compile(r"\\begin\{(?:p|b|v|V)matrix\}(.+?)\\end\{(?:p|b|v|V)matrix\}", re.DOTALL)

    def convert(match: re.Match[str]) -> str:
        rows = [row.strip() for row in match.group(1).split(r"\\") if row.strip()]
        return "(" + ",".join("(" + ",".join(cell.strip() for cell in row.split("&")) + ")" for row in rows) + ")"

    return pattern.sub(convert, text)


def normalize_latex_input(text: str) -> dict[str, Any]:
    """변수: 사용자 원문. 원리: 지원 LaTeX를 평문화하고 미지원 명령을 명시해 후속 라우터가 안전하게 거부하게 한다."""
    original = str(text or "")
    normalized = original.replace("$", "").replace(r"\[", "").replace(r"\]", "")
    normalized = _replace_matrix(normalized)
    normalized = _replace_fraction(normalized)
    normalized = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", normalized)
    normalized = re.sub(r"\\lim\s*_\{?\s*([a-zA-Z])\s*\\to\s*([^}\s]+)\s*\}?", r"lim \1->\2", normalized)
    normalized = re.sub(r"\\int\s*_\{?([^}^\s]+)\}?\s*\^\{?([^}\s]+)\}?", r"정적분 \1부터 \2", normalized)
    for command, replacement in _COMMAND_REPLACEMENTS.items():
        normalized = normalized.replace(command, replacement)
    normalized = _unwrap_braces(normalized)
    normalized = normalized.replace("\\,", " ").replace("\\!", "").replace("\\ ", " ")
    unsupported = sorted(set(re.findall(r"\\[a-zA-Z]+", normalized)))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return {"original": original, "normalized": normalized, "unsupported": unsupported, "supported": not unsupported}
