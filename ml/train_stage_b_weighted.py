"""Train Stage B with inverse-frequency weighted cross-entropy.

Stage A and the existing Stage B checkpoint are not modified. The weighted
checkpoint is written to ml/outputs_two_stage/stage_b_weighted/best_model.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from torch.nn import CrossEntropyLoss
from transformers import Trainer, TrainingArguments

ML_DIR = Path(__file__).resolve().parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from config import (
    BATCH_SIZE,
    LABEL_COLUMN,
    LABEL_TO_NAME,
    LEARNING_RATE,
    MAX_LENGTH,
    NUM_EPOCHS,
    RANDOM_SEED,
    STAGE_B_BEST_MODEL_DIR,
    STAGE_B_ID2LABEL,
    STAGE_B_LABEL2ID,
    STAGE_B_NUM_LABELS,
    STAGE_B_OUTPUT_DIR,
    TEST_CSV,
    TEXT_COLUMN,
    TRAIN_CSV,
    VALIDATION_CSV,
)
from train import RequirementDataset, resolve_model_source, set_seed, use_local_files
from train_two_stage import load_raw_rows, to_stage_b
from transformers import AutoModelForSequenceClassification, AutoTokenizer


DEFAULT_OUTPUT_DIR = STAGE_B_OUTPUT_DIR.parent / "stage_b_weighted"
DEFAULT_BEST_MODEL_DIR = DEFAULT_OUTPUT_DIR / "best_model"


class WeightedTrainer(Trainer):
    """Hugging Face Trainer using fixed Stage B class weights."""

    def __init__(self, *args, class_weights: torch.Tensor, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights.float()

    def compute_loss(
        self,
        model,
        inputs,
        return_outputs: bool = False,
        num_items_in_batch=None,
    ):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        loss = CrossEntropyLoss(weight=self.class_weights.to(logits.device))(
            logits.view(-1, logits.size(-1)), labels.view(-1)
        )
        return (loss, outputs) if return_outputs else loss


def _stage_b_rows(path: Path) -> list[dict]:
    return to_stage_b(load_raw_rows(path))


def class_weights(train_rows: list[dict]) -> tuple[torch.Tensor, Counter[int]]:
    counts = Counter(row[LABEL_COLUMN] for row in train_rows)
    total = len(train_rows)
    weights = torch.tensor(
        [total / (STAGE_B_NUM_LABELS * counts[index]) for index in range(STAGE_B_NUM_LABELS)],
        dtype=torch.float32,
    )
    return weights, counts


def _make_dataset(rows: list[dict], tokenizer) -> RequirementDataset:
    encodings = tokenizer(
        [row[TEXT_COLUMN] for row in rows],
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
    )
    return RequirementDataset(encodings, [row[LABEL_COLUMN] for row in rows])


def _evaluate_model(model, tokenizer, rows: list[dict], device: torch.device) -> dict:
    texts = [row[TEXT_COLUMN] for row in rows]
    labels = np.array([row[LABEL_COLUMN] for row in rows], dtype=int)
    encodings = tokenizer(
        texts,
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    loader = torch.utils.data.DataLoader(
        RequirementDataset(encodings, labels.tolist()),
        batch_size=BATCH_SIZE,
        shuffle=False,
    )
    predictions: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            predictions.append(
                torch.argmax(model(**{key: value for key, value in batch.items() if key != "labels"}).logits, dim=-1)
                .cpu()
                .numpy()
            )
    predicted = np.concatenate(predictions)
    precision, recall, f1, support = precision_recall_fscore_support(
        labels,
        predicted,
        labels=list(range(STAGE_B_NUM_LABELS)),
        average=None,
        zero_division=0,
    )
    return {
        "accuracy": float(accuracy_score(labels, predicted)),
        "macro_precision": float(np.mean(precision)),
        "macro_recall": float(np.mean(recall)),
        "macro_f1": float(np.mean(f1)),
        "per_class": {
            STAGE_B_ID2LABEL[index]: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
            }
            for index in range(STAGE_B_NUM_LABELS)
        },
        "confusion_matrix": confusion_matrix(
            labels,
            predicted,
            labels=list(range(STAGE_B_NUM_LABELS)),
        ).tolist(),
        "predicted": predicted.tolist(),
    }


def _print_metrics(name: str, metrics: dict) -> None:
    print(f"\n{name}")
    print(f"accuracy: {metrics['accuracy']:.4f}")
    print(f"macro_f1: {metrics['macro_f1']:.4f}")
    for label, values in metrics["per_class"].items():
        print(
            f"{label}: precision={values['precision']:.4f} "
            f"recall={values['recall']:.4f} f1={values['f1']:.4f} "
            f"support={values['support']}"
        )
    print("confusion_matrix rows=actual columns=predicted")
    print(metrics["confusion_matrix"])


def _print_fragment_metrics(rows: list[dict], predictions: list[int]) -> None:
    buckets = defaultdict(lambda: [0, 0, 0])
    for row, prediction in zip(rows, predictions):
        words = len(row[TEXT_COLUMN].split())
        bucket = "<=5 words" if words <= 5 else "6-15 words" if words <= 15 else ">15 words"
        buckets[bucket][0] += 1
        buckets[bucket][1] += int(row[LABEL_COLUMN] == prediction)
        buckets[bucket][2] += int(prediction == STAGE_B_LABEL2ID["pragmatic"])
    print("\nfragment_analysis")
    for bucket in ("<=5 words", "6-15 words", ">15 words"):
        total, correct, pragmatic = buckets[bucket]
        print(
            f"{bucket}: accuracy={correct / total:.4f} "
            f"predicted_pragmatic={pragmatic} total={total}"
        )


def train(output_dir: Path = DEFAULT_OUTPUT_DIR, best_model_dir: Path = DEFAULT_BEST_MODEL_DIR) -> None:
    started = time.perf_counter()
    set_seed(RANDOM_SEED)
    train_rows = _stage_b_rows(TRAIN_CSV)
    validation_rows = _stage_b_rows(VALIDATION_CSV)
    weights, counts = class_weights(train_rows)

    print("Stage B weighted training only")
    print(f"Model initialization: bert-base-uncased")
    print(f"Output: {best_model_dir}")
    print("model_index -> class_name -> count -> weight")
    for index in range(STAGE_B_NUM_LABELS):
        print(
            f"{index} -> {STAGE_B_ID2LABEL[index]} -> {counts[index]} -> "
            f"{weights[index].item():.4f}"
        )

    model_source = resolve_model_source()
    tokenizer = AutoTokenizer.from_pretrained(
        model_source,
        local_files_only=use_local_files(model_source),
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        model_source,
        num_labels=STAGE_B_NUM_LABELS,
        id2label=STAGE_B_ID2LABEL,
        label2id=STAGE_B_LABEL2ID,
        local_files_only=use_local_files(model_source),
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    output_dir.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(
        output_dir=str(output_dir),
        learning_rate=LEARNING_RATE,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        logging_strategy="epoch",
        save_total_limit=2,
        report_to="none",
        seed=RANDOM_SEED,
        dataloader_pin_memory=False,
    )
    trainer = WeightedTrainer(
        model=model,
        args=args,
        train_dataset=_make_dataset(train_rows, tokenizer),
        eval_dataset=_make_dataset(validation_rows, tokenizer),
        compute_metrics=__import__("train").compute_metrics,
        class_weights=weights,
    )
    trainer.train()
    best_model_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(best_model_dir))
    tokenizer.save_pretrained(str(best_model_dir))

    validation_metrics = _evaluate_model(trainer.model, tokenizer, validation_rows, device)
    test_rows = _stage_b_rows(TEST_CSV)
    test_metrics = _evaluate_model(trainer.model, tokenizer, test_rows, device)
    _print_metrics("validation", validation_metrics)
    _print_metrics("test", test_metrics)
    _print_fragment_metrics(test_rows, test_metrics.pop("predicted"))

    summary = {
        "class_counts": {STAGE_B_ID2LABEL[index]: counts[index] for index in range(STAGE_B_NUM_LABELS)},
        "class_weights": {STAGE_B_ID2LABEL[index]: round(float(weights[index]), 6) for index in range(STAGE_B_NUM_LABELS)},
        "validation": validation_metrics,
        "test": test_metrics,
        "training_seconds": round(time.perf_counter() - started, 2),
    }
    (output_dir / "weighted_evaluation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nTraining seconds: {summary['training_seconds']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--best-model-dir", type=Path, default=DEFAULT_BEST_MODEL_DIR)
    args = parser.parse_args()
    train(args.output_dir, args.best_model_dir)
