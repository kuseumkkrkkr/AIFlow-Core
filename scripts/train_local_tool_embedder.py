"""로컬 다국어 임베딩 모델을 AIFlow 도구 감지 용도로 파인튜닝한다.

입력 문항을 평균 풀링 임베딩으로 만들고 도구 분류 손실로 encoder를 미세조정한다.
학습 뒤에는 도구별 중심 벡터를 저장한다. 런타임은 새 문제와 중심 벡터의 코사인 유사도로
후보 도구를 고르므로, 정답을 생성하지 않고 도구 검색만 담당한다.
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
    classifier = nn.Linear(hidden_size, len(labels))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    encoder.to(device); classifier.to(device)
    optimizer = torch.optim.AdamW(list(encoder.parameters()) + list(classifier.parameters()), lr=2e-5)

    def collate(batch: list[dict[str, Any]]) -> dict[str, Any]:
        """변수: 레코드 묶음. 원리: E5의 query 접두어를 붙이고 토큰 길이를 제한해 메모리 사용을 일정하게 한다."""
        encoded = tokenizer(["query: " + str(item["question"]) for item in batch], padding=True, truncation=True, max_length=args.max_length, return_tensors="pt")
        encoded["labels"] = torch.tensor([label_to_id[item["tool_domain"]] for item in batch], dtype=torch.long)
        return encoded

    loader = DataLoader(records, batch_size=max(1, args.batch_size), shuffle=True, collate_fn=collate)
    encoder.train(); classifier.train()
    for _ in range(max(1, args.epochs)):
        for batch in loader:
            labels_tensor = batch.pop("labels").to(device)
            batch = {key: value.to(device) for key, value in batch.items()}
            output = encoder(**batch).last_hidden_state
            mask = batch["attention_mask"].unsqueeze(-1)
            vectors = (output * mask).sum(1) / mask.sum(1).clamp(min=1)
            loss = nn.functional.cross_entropy(classifier(vectors), labels_tensor)
            optimizer.zero_grad(); loss.backward(); optimizer.step()

    encoder.eval()
    grouped: dict[str, list[list[float]]] = defaultdict(list)
    with torch.no_grad():
        for record in records:
            batch = tokenizer("query: " + str(record["question"]), truncation=True, max_length=args.max_length, return_tensors="pt")
            batch = {key: value.to(device) for key, value in batch.items()}
            output = encoder(**batch).last_hidden_state; mask = batch["attention_mask"].unsqueeze(-1)
            vector = ((output * mask).sum(1) / mask.sum(1).clamp(min=1))[0].cpu().tolist()
            grouped[record["tool_domain"]].append(vector)
    prototypes = {label: [sum(values[index] for values in vectors) / len(vectors) for index in range(hidden_size)] for label, vectors in grouped.items()}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    encoder.save_pretrained(args.output_dir); tokenizer.save_pretrained(args.output_dir)
    (args.output_dir / "tool_prototypes.json").write_text(json.dumps({"base_model": args.model, "labels": labels, "prototypes": prototypes, "record_count": len(records)}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"records": len(records), "labels": len(labels), "device": str(device), "output": str(args.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
