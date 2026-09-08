"""Final evaluation for the BERT baseline.

Loads the saved best checkpoint and scores a split. Default is untouched
test.csv. This script must not be used to retune hyperparameters.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from config import (
    BATCH_SIZE,
    BEST_MODEL_DIR,
    ID2LABEL,
    LABEL_COLUMN,
    LABEL_TO_FULL_NAME,
    LABEL_TO_NAME,
    MAX_LENGTH,
    NUM_LABELS,
    OUTPUT_DIR,
    RANDOM_SEED,
    TEST_CSV,
    TEXT_COLUMN,
    VALIDATION_CSV,
    WEIGHTED_BEST_MODEL_DIR,
    WEIGHTED_OUTPUT_DIR,
)
from train import RequirementDataset, load_split, set_seed


def predict(model, tokenizer, rows: list[dict], device: torch.device) -> np.ndarray:
    texts = [row[TEXT_COLUMN] for row in rows]
    labels = [row[LABEL_COLUMN] for row in rows]
    encodings = tokenizer(
        texts,
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
    )
    dataset = RequirementDataset(encodings, labels)
    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    model.eval()
    preds = []
    with torch.no_grad():
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            outputs = model(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
            )
            logits = outputs.logits
            preds.append(torch.argmax(logits, dim=-1).cpu().numpy())
    return np.concatenate(preds, axis=0)


def write_csv(path: Path, fieldnames: list[str], records: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def evaluate_split(
    split_name: str,
    csv_path: Path,
    model_dir: Path = BEST_MODEL_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> dict:
    if not model_dir.exists():
        raise FileNotFoundError(
            f"Best model not found at {model_dir}. Train first with ml/train.py."
        )

    set_seed(RANDOM_SEED)
    device = torch.device("cpu")
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    model.to(device)

    rows = load_split(csv_path)
    y_true = np.array([row[LABEL_COLUMN] for row in rows], dtype=int)
    y_pred = predict(model, tokenizer, rows, device)

    accuracy = accuracy_score(y_true, y_pred)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        average="macro",
        zero_division=0,
    )
    per_p, per_r, per_f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=list(range(NUM_LABELS)),
        average=None,
        zero_division=0,
    )
    cm = confusion_matrix(y_true, y_pred, labels=list(range(NUM_LABELS)))
    report = classification_report(
        y_true,
        y_pred,
        labels=list(range(NUM_LABELS)),
        target_names=[ID2LABEL[i] for i in range(NUM_LABELS)],
        zero_division=0,
        digits=4,
    )

    class_names = [ID2LABEL[i] for i in range(NUM_LABELS)]
    per_class_records = []
    for index in range(NUM_LABELS):
        dataset_label = index + 1
        per_class_records.append(
            {
                "dataset_label": dataset_label,
                "name": ID2LABEL[index],
                "full_name": LABEL_TO_FULL_NAME[dataset_label],
                "precision": float(per_p[index]),
                "recall": float(per_r[index]),
                "f1": float(per_f1[index]),
                "support": int(support[index]),
            }
        )

    cm_records = []
    for i, true_name in enumerate(class_names):
        row = {"true_label": true_name}
        for j, pred_name in enumerate(class_names):
            row[f"pred_{pred_name}"] = int(cm[i, j])
        cm_records.append(row)

    misclassified = []
    for row, true_id, pred_id in zip(rows, y_true, y_pred):
        if true_id == pred_id:
            continue
        true_label = int(true_id) + 1
        pred_label = int(pred_id) + 1
        misclassified.append(
            {
                "requirement": row[TEXT_COLUMN],
                "true_dataset_label": true_label,
                "true_name": LABEL_TO_NAME[true_label],
                "pred_dataset_label": pred_label,
                "pred_name": LABEL_TO_NAME[pred_label],
                "syntactic_syntax_confusion": int(
                    {true_label, pred_label} == {2, 4}
                ),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    metrics = {
        "split": split_name,
        "n_rows": len(rows),
        "accuracy": float(accuracy),
        "macro_precision": float(macro_p),
        "macro_recall": float(macro_r),
        "macro_f1": float(macro_f1),
        "per_class": per_class_records,
        "syntactic_syntax_confusion_count": sum(
            item["syntactic_syntax_confusion"] for item in misclassified
        ),
        "n_misclassified": len(misclassified),
    }
    (output_dir / f"{split_name}_metrics.json").write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )
    (output_dir / f"{split_name}_classification_report.txt").write_text(
        report,
        encoding="utf-8",
    )
    write_csv(
        output_dir / f"{split_name}_per_class_metrics.csv",
        [
            "dataset_label",
            "name",
            "full_name",
            "precision",
            "recall",
            "f1",
            "support",
        ],
        per_class_records,
    )
    write_csv(
        output_dir / f"{split_name}_confusion_matrix.csv",
        ["true_label"] + [f"pred_{name}" for name in class_names],
        cm_records,
    )
    write_csv(
        output_dir / f"{split_name}_misclassified.csv",
        [
            "requirement",
            "true_dataset_label",
            "true_name",
            "pred_dataset_label",
            "pred_name",
            "syntactic_syntax_confusion",
        ],
        misclassified,
    )

    print(f"Split: {split_name} ({csv_path})")
    print(f"Rows: {len(rows)}")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Macro precision: {macro_p:.4f}")
    print(f"Macro recall: {macro_r:.4f}")
    print(f"Macro F1: {macro_f1:.4f}")
    print("\nPer-class metrics:")
    for rec in per_class_records:
        print(
            f"  {rec['dataset_label']} {rec['name']}: "
            f"P={rec['precision']:.4f} R={rec['recall']:.4f} "
            f"F1={rec['f1']:.4f} n={rec['support']}"
        )
    print("\nConfusion matrix (rows=true, cols=pred):")
    header = "true\\pred".ljust(12) + "".join(name[:10].ljust(12) for name in class_names)
    print(header)
    for i, true_name in enumerate(class_names):
        print(true_name[:10].ljust(12) + "".join(str(cm[i, j]).ljust(12) for j in range(NUM_LABELS)))
    print(
        f"\nMisclassified: {len(misclassified)} "
        f"(syntactic<->syntax: {metrics['syntactic_syntax_confusion_count']})"
    )
    print(f"Artifacts written under {output_dir}")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the saved BERT baseline.")
    parser.add_argument(
        "--split",
        choices=("test", "validation"),
        default="test",
        help="test.csv is the default and must remain the final held-out evaluation.",
    )
    parser.add_argument(
        "--experiment",
        choices=("baseline", "weighted"),
        default="baseline",
        help="baseline = unweighted BERT; weighted = class-weighted loss run.",
    )
    args = parser.parse_args()
    csv_path = TEST_CSV if args.split == "test" else VALIDATION_CSV
    if args.experiment == "weighted":
        model_dir, output_dir = WEIGHTED_BEST_MODEL_DIR, WEIGHTED_OUTPUT_DIR
    else:
        model_dir, output_dir = BEST_MODEL_DIR, OUTPUT_DIR
    if args.split == "test":
        print("Final evaluation on untouched test.csv.")
        print("This run must not be used to retune the model.")
    evaluate_split(args.split, csv_path, model_dir=model_dir, output_dir=output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
