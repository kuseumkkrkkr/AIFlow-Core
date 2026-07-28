"""외부 의존성 없이 저장소 가중치로 동작하는 소형 MLP 도구 라우터.

학습 입력은 도구 계약의 설명·키워드와 결정론적 패러프레이즈이며, 실제 기출
코퍼스는 학습에 쓰지 않는다. Vercel 런타임에서는 저장된 가중치를 읽어 추론만 한다.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any


MODEL_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "mini_neural_router_v1.json"
MODEL_VERSION = "mini-neural-router-v1"
FEATURE_SIZE = 96
HIDDEN_SIZE = 24


def _features(text: str) -> list[float]:
    """변수: 정규화 문제. 원리: 문자 2·3-gram을 고정 차원으로 해싱해 경량 MLP의 입력 벡터를 만든다."""
    compact = "".join(str(text).lower().split())
    vector = [0.0] * FEATURE_SIZE
    for width in (2, 3):
        for index in range(max(0, len(compact) - width + 1)):
            token = compact[index:index + width]
            bucket = sum((position + 1) * ord(char) for position, char in enumerate(token)) % FEATURE_SIZE
            vector[bucket] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _softmax(values: list[float]) -> list[float]:
    """변수: 출력 로그릿. 원리: 수치 안정화 후 확률 분포로 변환한다."""
    maximum = max(values)
    exps = [math.exp(value - maximum) for value in values]
    total = sum(exps)
    return [value / total for value in exps]


def _forward(model: dict[str, Any], features: list[float]) -> tuple[list[float], list[float]]:
    """변수: 가중치·입력 특징. 원리: ReLU 은닉층 뒤 softmax 출력층으로 도구별 확률을 계산한다."""
    hidden = [max(0.0, model["b1"][unit] + sum(features[index] * model["w1"][index][unit] for index in range(FEATURE_SIZE))) for unit in range(HIDDEN_SIZE)]
    logits = [model["b2"][label] + sum(hidden[unit] * model["w2"][unit][label] for unit in range(HIDDEN_SIZE)) for label in range(len(model["domains"]))]
    return hidden, _softmax(logits)


def train_profile_model() -> dict[str, Any]:
    """변수: route spec. 원리: 계약 예시만으로 작은 MLP를 결정론 학습해 기출 누수를 막는다."""
    from tool_routing import ROUTE_SPECS

    domains = [spec.domain for spec in ROUTE_SPECS]
    samples: list[tuple[list[float], int]] = []
    for label, spec in enumerate(ROUTE_SPECS):
        keywords = " ".join(spec.keywords)
        for text in (spec.description, keywords, f"{spec.description} {keywords}"):
            samples.append((_features(text), label))
    # 고정 시드 LCG로 초기화해 빌드마다 같은 가중치가 나온다.
    state = 20260728
    def random_weight() -> float:
        nonlocal state
        state = (1103515245 * state + 12345) % (2 ** 31)
        return ((state / (2 ** 31)) - 0.5) * 0.08

    model: dict[str, Any] = {
        "version": MODEL_VERSION, "domains": domains,
        "w1": [[random_weight() for _ in range(HIDDEN_SIZE)] for _ in range(FEATURE_SIZE)], "b1": [0.01] * HIDDEN_SIZE,
        "w2": [[random_weight() for _ in domains] for _ in range(HIDDEN_SIZE)], "b2": [0.0] * len(domains),
    }
    learning_rate = 0.18
    for _ in range(160):
        for features, target in samples:
            hidden, probabilities = _forward(model, features)
            output_delta = [probability - float(index == target) for index, probability in enumerate(probabilities)]
            hidden_delta = [sum(output_delta[label] * model["w2"][unit][label] for label in range(len(domains))) * float(hidden[unit] > 0) for unit in range(HIDDEN_SIZE)]
            for unit in range(HIDDEN_SIZE):
                for label in range(len(domains)):
                    model["w2"][unit][label] -= learning_rate * hidden[unit] * output_delta[label]
            for label in range(len(domains)):
                model["b2"][label] -= learning_rate * output_delta[label]
            for index in range(FEATURE_SIZE):
                for unit in range(HIDDEN_SIZE):
                    model["w1"][index][unit] -= learning_rate * features[index] * hidden_delta[unit]
            for unit in range(HIDDEN_SIZE):
                model["b1"][unit] -= learning_rate * hidden_delta[unit]
    return model


@lru_cache(maxsize=1)
def load_model() -> dict[str, Any]:
    """변수: 저장소 모델 경로. 원리: UTF-8 가중치 JSON을 한 번만 메모리에 올려 요청별 파일 I/O를 막는다."""
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    if model.get("version") != MODEL_VERSION or len(model.get("domains", [])) == 0:
        raise ValueError("미니 신경망 모델 계약이 올바르지 않습니다.")
    return model


def neural_probabilities(text: str) -> dict[str, float]:
    """변수: 문제 텍스트. 원리: 저장된 MLP의 softmax 확률을 domain별 사전으로 반환한다."""
    model = load_model()
    _, probabilities = _forward(model, _features(text))
    return dict(zip(model["domains"], probabilities, strict=True))


if __name__ == "__main__":
    """CLI: 계약 프로파일로 가중치를 재생성해 UTF-8 JSON 모델 파일을 저장한다."""
    output = train_profile_model()
    MODEL_PATH.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"MODEL domains={len(output['domains'])} path={MODEL_PATH}")
