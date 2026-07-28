"""로컬 다국어 임베딩 모델을 AIFlow 도구 감지 용도로 경량 파인튜닝한다.

입력 문항의 E5 평균 풀링 벡터를 고정하고, 작은 투영층과 분류 헤드를 도구 분류 손실로
학습한다. 전체 인코더를 CPU에서 역전파하면 수 GB 메모리가 필요하므로, 이 방식은
로컬 PC에서도 도메인 라우팅 공간을 안전하게 파인튜닝한다. 학습 뒤 도구 중심 벡터와
투영층을 저장하며, 런타임은 새 문제와 중심 벡터의 코사인 유사도로 후보를 고른다.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _load_records(path: Path, minimum_per_label: int) -> tuple[list[dict[str, Any]], list[str]]:
    """변수: JSONL 레코드·최소 라벨 수. 원리: 희소 도구를 제외하고 재현 가능한 라벨 사전을 만든다."""
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    counts = Counter(str(record["tool_domain"]) for record in records)
    labels = sorted(label for label, count in counts.items() if count >= minimum_per_label)
    return [record for record in records if record["tool_domain"] in labels], labels


def main() -> int:
    """변수: 모델명·학습셋·출력 경로. 원리: CPU/GPU 공통 PyTorch로 분류 미세조정 후 도구 중심 임베딩을 저장한다."""
    parser = argparse.ArgumentParser(description="AIFlow 로컬 도구 감지 임베더 파인튜닝")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="intfloat/multilingual-e5-small")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=192)
    parser.add_argument("--minimum-per-label", type=int, default=4)
    parser.add_argument("--projection-size", type=int, default=128)
    args = parser.parse_args()
    import torch
    from torch import nn
    from torch.utils.data import DataLoader
    from transformers import AutoModel, AutoTokenizer

    records, labels = _load_records(args.dataset, args.minimum_per_label)
    if len(records) < 64 or len(labels) < 2:
        raise ValueError("검증된 학습 문항 64개와 도구 라벨 2개 이상이 필요합니다.")
    random.Random(20260728).shuffle(records)
    label_to_id = {label: index for index, label in enumerate(labels)}
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    encoder = AutoModel.from_pretrained(args.model)
    hidden_size = int(encoder.config.hidden_size)
    projection = nn.Linear(hidden_size, max(8, args.projection_size))
    classifier = nn.Linear(max(8, args.projection_size), len(labels))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # CPU 전체 역전파는 수 GB 메모리를 요구하므로 E5는 고정하고 도메인 투영층만 학습한다.
    encoder.requires_grad_(False); encoder.to(device); encoder.eval()
    projection.to(device); classifier.to(device)
    optimizer = torch.optim.AdamW(list(projection.parameters()) + list(classifier.parameters()), lr=2e-4)

    def collate(batch: list[dict[str, Any]]) -> dict[str, Any]:
        """변수: 레코드 묶음. 원리: E5의 query 접두어를 붙이고 토큰 길이를 제한해 메모리 사용을 일정하게 한다."""
        encoded = tokenizer(["query: " + str(item["question"]) for item in batch], padding=True, truncation=True, max_length=args.max_length, return_tensors="pt")
        encoded["labels"] = torch.tensor([label_to_id[item["tool_domain"]] for item in batch], dtype=torch.long)
        return encoded

    loader = DataLoader(records, batch_size=max(1, args.batch_size), shuffle=True, collate_fn=collate)
    projection.train(); classifier.train()
    for _ in range(max(1, args.epochs)):
        for batch in loader:
            labels_tensor = batch.pop("labels").to(device)
            batch = {key: value.to(device) for key, value in batch.items()}
            with torch.no_grad():
                output = encoder(**batch).last_hidden_state
                mask = batch["attention_mask"].unsqueeze(-1)
                vectors = (output * mask).sum(1) / mask.sum(1).clamp(min=1)
            loss = nn.functional.cross_entropy(classifier(projection(vectors)), labels_tensor)
            optimizer.zero_grad(); loss.backward(); optimizer.step()

    projection.eval()
    grouped: dict[str, list[list[float]]] = defaultdict(list)
    with torch.no_grad():
        for record in records:
            batch = tokenizer("query: " + str(record["question"]), truncation=True, max_length=args.max_length, return_tensors="pt")
            batch = {key: value.to(device) for key, value in batch.items()}
            output = encoder(**batch).last_hidden_state; mask = batch["attention_mask"].unsqueeze(-1)
            vector = projection((output * mask).sum(1) / mask.sum(1).clamp(min=1))[0].cpu().tolist()
            grouped[record["tool_domain"]].append(vector)
    # 중심 벡터는 고정 E5 원공간이 아니라 학습한 도메인 투영 공간의 차원을 따른다.
    projection_size = len(next(iter(grouped.values()))[0])
    prototypes = {label: [sum(values[index] for values in vectors) / len(vectors) for index in range(projection_size)] for label, vectors in grouped.items()}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    encoder.save_pretrained(args.output_dir); tokenizer.save_pretrained(args.output_dir)
    projection_data = {"weight": projection.weight.detach().cpu().tolist(), "bias": projection.bias.detach().cpu().tolist()}
    (args.output_dir / "tool_prototypes.json").write_text(json.dumps({"base_model": args.model, "labels": labels, "prototypes": prototypes, "record_count": len(records), "training_mode": "frozen-e5-domain-projection-v1", "projection": projection_data}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"records": len(records), "labels": len(labels), "device": str(device), "training_mode": "frozen-e5-domain-projection-v1", "output": str(args.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
