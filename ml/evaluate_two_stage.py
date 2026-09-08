"""Evaluate the two-stage BERT pipeline.

Stage A and Stage B checkpoints are loaded from ml/outputs_two_stage/.
Test.csv is used only for final reporting, not for model selection.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
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
    ID2LABEL,
    LABEL_COLUMN,
    LABEL_TO_FULL_NAME,
    LABEL_TO_NAME,
    MAX_LENGTH,
    NUM_LABELS,
    RANDOM_SEED,
    STAGE_A_BEST_MODEL_DIR,
    STAGE_A_ID2LABEL,
    STAGE_B_BEST_MODEL_DIR,
    STAGE_B_ID2LABEL,
    TEST_CSV,
    TEXT_COLUMN,
    TWO_STAGE_OUTPUT_DIR,
    VALIDATION_CSV,
)
from evaluate import write_csv
from train import RequirementDataset, set_seed
from train_two_stage import load_raw_rows, to_stage_a, to_stage_b


def predict_ids(
    model,
    tokenizer,
    texts: list[str],
    device: torch.device,
) -> np.ndarray:
    encodings = tokenizer(
        texts,
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
    )
    dataset = RequirementDataset(encodings, [0] * len(texts))
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
            preds.append(torch.argmax(outputs.logits, dim=-1).cpu().numpy())
    return np.concatenate(preds, axis=0)


def metrics_bundle(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    id2label: dict[int, str],
    label_offset: int = 0,
) -> dict:
    num_labels = len(id2label)
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
        labels=list(range(num_labels)),
        average=None,
        zero_division=0,
    )
    cm = confusion_matrix(y_true, y_pred, labels=list(range(num_labels)))
    per_class = []
    for index in range(num_labels):
        dataset_label = index + label_offset
        per_class.append(
            {
                "stage_index": index,
                "dataset_label": dataset_label if label_offset else "",
                "name": id2label[index],
                "full_name": LABEL_TO_FULL_NAME.get(
                    dataset_label,
                    id2label[index],
                ),
                "precision": float(per_p[index]),
                "recall": float(per_r[index]),
                "f1": float(per_f1[index]),
                "support": int(support[index]),
            }
        )
    return {
        "n_rows": int(len(y_true)),
        "accuracy": float(accuracy),
        "macro_precision": float(macro_p),
        "macro_recall": float(macro_r),
        "macro_f1": float(macro_f1),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "classification_report": classification_report(
            y_true,
            y_pred,
            labels=list(range(num_labels)),
            target_names=[id2label[i] for i in range(num_labels)],
            zero_division=0,
            digits=4,
        ),
    }


def print_bundle(title: str, bundle: dict) -> None:
    print(f"\n{title}")
    print(f"  Rows: {bundle['n_rows']}")
    print(f"  Accuracy: {bundle['accuracy']:.4f}")
    print(f"  Macro precision: {bundle['macro_precision']:.4f}")
    print(f"  Macro recall: {bundle['macro_recall']:.4f}")
    print(f"  Macro F1: {bundle['macro_f1']:.4f}")
    for rec in bundle["per_class"]:
        print(
            f"    {rec['name']}: P={rec['precision']:.4f} "
            f"R={rec['recall']:.4f} F1={rec['f1']:.4f} n={rec['support']}"
        )


def write_bundle(prefix: Path, bundle: dict, class_names: list[str]) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    serializable = dict(bundle)
    (prefix.parent / f"{prefix.name}_metrics.json").write_text(
        json.dumps(serializable, indent=2),
        encoding="utf-8",
    )
    (prefix.parent / f"{prefix.name}_classification_report.txt").write_text(
        bundle["classification_report"],
        encoding="utf-8",
    )
    write_csv(
        prefix.parent / f"{prefix.name}_per_class_metrics.csv",
        [
            "stage_index",
            "dataset_label",
            "name",
            "full_name",
            "precision",
            "recall",
            "f1",
            "support",
        ],
        bundle["per_class"],
    )
    cm = np.array(bundle["confusion_matrix"])
    cm_records = []
    for i, true_name in enumerate(class_names):
        record = {"true_label": true_name}
        for j, pred_name in enumerate(class_names):
            record[f"pred_{pred_name}"] = int(cm[i, j])
        cm_records.append(record)
    write_csv(
        prefix.parent / f"{prefix.name}_confusion_matrix.csv",
        ["true_label"] + [f"pred_{name}" for name in class_names],
        cm_records,
    )


def evaluate_stage(
    title: str,
    model,
    tokenizer,
    rows: list[dict],
    device: torch.device,
    id2label: dict[int, str],
    label_offset: int,
    output_prefix: Path,
) -> dict:
    texts = [row[TEXT_COLUMN] for row in rows]
    y_true = np.array([row[LABEL_COLUMN] for row in rows], dtype=int)
    y_pred = predict_ids(model, tokenizer, texts, device)
    bundle = metrics_bundle(y_true, y_pred, id2label, label_offset=label_offset)
    print_bundle(title, bundle)
    write_bundle(output_prefix, bundle, [id2label[i] for i in sorted(id2label)])
    return bundle


def pipeline_predict(
    stage_a,
    stage_b,
    tokenizer_a,
    tokenizer_b,
    texts: list[str],
    device: torch.device,
) -> np.ndarray:
    """Return dataset labels 1-6. Stage A 0 -> clean(6); 1 -> Stage B + 1."""
    a_pred = predict_ids(stage_a, tokenizer_a, texts, device)
    final = np.full(len(texts), 6, dtype=int)
    ambiguous_idx = np.where(a_pred == 1)[0]
    if len(ambiguous_idx):
        amb_texts = [texts[i] for i in ambiguous_idx]
        b_pred = predict_ids(stage_b, tokenizer_b, amb_texts, device)
        final[ambiguous_idx] = b_pred + 1
    return final


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the two-stage BERT pipeline."
    )
    parser.add_argument(
        "--split",
        choices=("test", "validation", "both"),
        default="both",
        help="Which split(s) to score. Model selection already happened on validation.",
    )
    args = parser.parse_args()

    if not STAGE_A_BEST_MODEL_DIR.exists() or not STAGE_B_BEST_MODEL_DIR.exists():
        raise FileNotFoundError(
            "Train both stages first with ml/train_two_stage.py."
        )

    set_seed(RANDOM_SEED)
    device = torch.device("cpu")
    TWO_STAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tokenizer_a = AutoTokenizer.from_pretrained(STAGE_A_BEST_MODEL_DIR)
    tokenizer_b = AutoTokenizer.from_pretrained(STAGE_B_BEST_MODEL_DIR)
    stage_a = AutoModelForSequenceClassification.from_pretrained(
        STAGE_A_BEST_MODEL_DIR
    ).to(device)
    stage_b = AutoModelForSequenceClassification.from_pretrained(
        STAGE_B_BEST_MODEL_DIR
    ).to(device)

    targets = []
    if args.split in ("validation", "both"):
        targets.append(("validation", VALIDATION_CSV, False))
    if args.split in ("test", "both"):
        targets.append(("test", TEST_CSV, True))

    pipeline_test = None
    for split_name, csv_path, is_test in targets:
        if is_test:
            print(f"\nFinal evaluation on untouched {csv_path.name}.")
            print("This run must not be used to retune the model.")

        raw_rows = load_raw_rows(csv_path)
        evaluate_stage(
            f"Stage A {split_name} (clean vs ambiguous)",
            stage_a,
            tokenizer_a,
            to_stage_a(raw_rows),
            device,
            STAGE_A_ID2LABEL,
            label_offset=0,
            output_prefix=TWO_STAGE_OUTPUT_DIR / f"stage_a_{split_name}",
        )
        evaluate_stage(
            f"Stage B {split_name} (ambiguous rows only)",
            stage_b,
            tokenizer_b,
            to_stage_b(raw_rows),
            device,
            STAGE_B_ID2LABEL,
            label_offset=1,
            output_prefix=TWO_STAGE_OUTPUT_DIR / f"stage_b_{split_name}",
        )

        texts = [row[TEXT_COLUMN] for row in raw_rows]
        y_true_dataset = np.array(
            [row["dataset_label"] for row in raw_rows],
            dtype=int,
        )
        y_pred_dataset = pipeline_predict(
            stage_a,
            stage_b,
            tokenizer_a,
            tokenizer_b,
            texts,
            device,
        )
        y_true_idx = y_true_dataset - 1
        y_pred_idx = y_pred_dataset - 1
        bundle = metrics_bundle(
            y_true_idx,
            y_pred_idx,
            ID2LABEL,
            label_offset=1,
        )

        true_bin = (y_true_dataset != 6).astype(int)
        pred_bin = (y_pred_dataset != 6).astype(int)
        clean_to_amb = int(((true_bin == 0) & (pred_bin == 1)).sum())
        amb_to_clean = int(((true_bin == 1) & (pred_bin == 0)).sum())

        pair_counts = Counter()
        misclassified = []
        for row, true_label, pred_label in zip(
            raw_rows,
            y_true_dataset,
            y_pred_dataset,
        ):
            if true_label == pred_label:
                continue
            pair_counts[(int(true_label), int(pred_label))] += 1
            misclassified.append(
                {
                    "requirement": row[TEXT_COLUMN],
                    "true_dataset_label": int(true_label),
                    "true_name": LABEL_TO_NAME[int(true_label)],
                    "pred_dataset_label": int(pred_label),
                    "pred_name": LABEL_TO_NAME[int(pred_label)],
                    "clean_to_ambiguous": int(
                        true_label == 6 and pred_label != 6
                    ),
                    "ambiguous_to_clean": int(
                        true_label != 6 and pred_label == 6
                    ),
                }
            )

        pair_rows = []
        n_errors = len(misclassified)
        for (true_label, pred_label), count in sorted(
            pair_counts.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        ):
            pair_rows.append(
                {
                    "true_dataset_label": true_label,
                    "true_name": LABEL_TO_NAME[true_label],
                    "pred_dataset_label": pred_label,
                    "pred_name": LABEL_TO_NAME[pred_label],
                    "count": count,
                    "percent_of_errors": (
                        round(100.0 * count / n_errors, 2) if n_errors else 0.0
                    ),
                }
            )

        bundle["clean_to_ambiguous"] = clean_to_amb
        bundle["ambiguous_to_clean"] = amb_to_clean
        bundle["n_misclassified"] = n_errors
        print_bundle(f"Two-stage pipeline {split_name} (6-class)", bundle)
        print(f"  clean -> ambiguous: {clean_to_amb}")
        print(f"  ambiguous -> clean: {amb_to_clean}")

        write_bundle(
            TWO_STAGE_OUTPUT_DIR / f"{split_name}",
            bundle,
            [ID2LABEL[i] for i in range(NUM_LABELS)],
        )
        write_csv(
            TWO_STAGE_OUTPUT_DIR / f"{split_name}_confusion_pairs.csv",
            [
                "true_dataset_label",
                "true_name",
                "pred_dataset_label",
                "pred_name",
                "count",
                "percent_of_errors",
            ],
            pair_rows,
        )
        write_csv(
            TWO_STAGE_OUTPUT_DIR / f"{split_name}_misclassified.csv",
            [
                "requirement",
                "true_dataset_label",
                "true_name",
                "pred_dataset_label",
                "pred_name",
                "clean_to_ambiguous",
                "ambiguous_to_clean",
            ],
            misclassified,
        )
        if is_test:
            pipeline_test = bundle

    if pipeline_test is not None:
        print("\nArtifacts written under", TWO_STAGE_OUTPUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
