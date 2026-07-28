"""비공개 로컬 임베더로 도구 후보를 검색하는 실험 3 모듈.

Vercel 기본 경로에는 모델 가중치와 transformers 의존성을 넣지 않는다. 따라서
로컬 체크포인트가 있을 때만 실제 임베딩을 계산하며, 없는 배포 환경에서는 호출자가
명시적으로 결정론적 문자 n-gram 기준선으로 대체할 수 있게 None을 반환한다.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from math import sqrt
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = ROOT / "private_models" / "tool-embedder-v1"


def _model_dir() -> Path:
    """변수: AIFLOW_LOCAL_EMBEDDER_DIR 환경 변수. 원리: 기본 D 작업본과 별도 체크포인트 경로를 모두 허용한다."""
    return Path(os.environ.get("AIFLOW_LOCAL_EMBEDDER_DIR", str(DEFAULT_MODEL_DIR)))


def local_embedder_available() -> bool:
    """변수: 로컬 체크포인트 경로. 원리: 모델·토크나이저·도구 중심 벡터가 모두 있을 때만 무거운 의존성을 로드한다."""
    directory = _model_dir()
    return all((directory / name).is_file() for name in ("config.json", "tool_prototypes.json"))


@lru_cache(maxsize=1)
def _load_local_embedder() -> tuple[Any, Any, dict[str, list[float]], dict[str, list[list[float]] | list[float]], str]:
    """변수: 비공개 모델 디렉터리. 원리: 프로세스당 한 번만 CPU 모델과 중심 벡터를 읽어 요청별 재로딩을 막는다."""
    if not local_embedder_available():
        raise FileNotFoundError("로컬 임베더 체크포인트가 없습니다.")
    import torch
    from transformers import AutoModel, AutoTokenizer

    directory = _model_dir()
    metadata = json.loads((directory / "tool_prototypes.json").read_text(encoding="utf-8"))
    prototypes = {str(domain): [float(value) for value in vector] for domain, vector in metadata["prototypes"].items()}
    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True)
    model = AutoModel.from_pretrained(directory, local_files_only=True)
    model.eval()
    projection = metadata.get("projection")
    if not isinstance(projection, dict) or not isinstance(projection.get("weight"), list) or not isinstance(projection.get("bias"), list):
        raise ValueError("도메인 투영층이 없는 로컬 임베더 체크포인트입니다.")
    return tokenizer, model, prototypes, projection, str(metadata.get("training_mode", metadata.get("base_model", "local-tool-embedder")))


def local_embedding_scores(text: str) -> dict[str, float] | None:
    """변수: 정규화 문제 문자열. 원리: 평균 풀링한 문항 벡터와 도구 중심 벡터의 코사인 유사도를 반환하며, 미설치 환경은 None으로 구분한다."""
    if not local_embedder_available():
        return None
    try:
        import torch
        tokenizer, model, prototypes, projection, _ = _load_local_embedder()
        encoded = tokenizer("query: " + text, truncation=True, max_length=192, return_tensors="pt")
        with torch.no_grad():
            output = model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1)
            raw_vector = ((output * mask).sum(1) / mask.sum(1).clamp(min=1))[0].tolist()
        weight = projection["weight"]
        bias = projection["bias"]
        vector = [sum(left * right for left, right in zip(row, raw_vector)) + float(offset) for row, offset in zip(weight, bias)]
        vector_norm = sqrt(sum(value * value for value in vector))
        if vector_norm == 0:
            return None
        return {
            domain: sum(left * right for left, right in zip(vector, prototype)) / (vector_norm * sqrt(sum(value * value for value in prototype)))
            for domain, prototype in prototypes.items()
            if prototype and sqrt(sum(value * value for value in prototype)) > 0
        }
    except (FileNotFoundError, ImportError, KeyError, OSError, ValueError):
        # 배포 환경의 의존성 부재와 손상된 개인 체크포인트는 풀이 실패가 아니라 실험 3 미사용 상태다.
        return None


def local_embedder_model_version() -> str:
    """변수: tool_prototypes.json 메타데이터. 원리: API와 실험 보고서가 실제 로컬 모델 기반 여부를 식별한다."""
    if not local_embedder_available():
        return "local-embedder-unavailable"
    try:
        metadata = json.loads((_model_dir() / "tool_prototypes.json").read_text(encoding="utf-8"))
        return str(metadata.get("training_mode", metadata.get("base_model", "local-tool-embedder")))
    except (FileNotFoundError, KeyError, OSError, ValueError, json.JSONDecodeError):
        return "local-embedder-unavailable"
