"""Error analysis for the class-weighted BERT model.

Loads the saved weighted checkpoint and scores the untouched test split.
Does not train, does not modify any dataset file, and does not overwrite
baseline or weighted experiment artifacts.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from config import (
    BATCH_SIZE,
    ERROR_ANALYSIS_DIR,
    ID2LABEL,
    LABEL_COLUMN,
    LABEL_TO_FULL_NAME,
    LABEL_TO_NAME,
    MAX_LENGTH,
    NUM_LABELS,
    RANDOM_SEED,
    TEST_CSV,
    TEXT_COLUMN,
    WEIGHTED_BEST_MODEL_DIR,
)
from evaluate import write_csv
from train import RequirementDataset, load_split, set_seed

EXAMPLES_PER_CLASS = 5
AMBIGUOUS_LABELS = {1, 2, 3, 4, 5}
CLEAN_LABEL = 6

FOCUSED_UNDIRECTED = {
    frozenset({1, 2}): "lexical_syntactic",
    frozenset({2, 4}): "syntactic_syntax",
    frozenset({3, 4}): "semantic_syntax",
}


def token_count(text: str) -> int:
    return len(text.split())


def confusion_group(true_label: int, pred_label: int) -> str:
    pair = frozenset({true_label, pred_label})
    if pair in FOCUSED_UNDIRECTED:
        return FOCUSED_UNDIRECTED[pair]
    if true_label in AMBIGUOUS_LABELS and pred_label == CLEAN_LABEL:
        return "ambiguous_to_clean"
    if true_label == CLEAN_LABEL and pred_label in AMBIGUOUS_LABELS:
        return "clean_to_ambiguous"
    return "other"


def predict_with_proba(
    model,
    tokenizer,
    rows: list[dict],
    device: torch.device,
) -> tuple[np.ndarray, np.ndarray]:
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
    pred_batches = []
    prob_batches = []
    with torch.no_grad():
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            outputs = model(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
            )
            probs = torch.softmax(outputs.logits, dim=-1)
            pred_batches.append(torch.argmax(probs, dim=-1).cpu().numpy())
            prob_batches.append(probs.cpu().numpy())

    return np.concatenate(pred_batches, axis=0), np.concatenate(prob_batches, axis=0)


def example_record(
    requirement: str,
    true_id: int,
    pred_id: int,
    probs: np.ndarray,
) -> dict:
    true_label = int(true_id) + 1
    pred_label = int(pred_id) + 1
    return {
        "requirement": requirement,
        "true_dataset_label": true_label,
        "true_name": LABEL_TO_NAME[true_label],
        "pred_dataset_label": pred_label,
        "pred_name": LABEL_TO_NAME[pred_label],
        "pred_confidence": float(probs[pred_id]),
        "true_class_probability": float(probs[true_id]),
        "confusion_group": confusion_group(true_label, pred_label),
        "token_count": token_count(requirement),
    }


def pick_examples(records: list[dict], limit: int) -> list[dict]:
    ranked = sorted(
        records,
        key=lambda item: item["pred_confidence"],
        reverse=True,
    )
    return ranked[:limit]


def main() -> int:
    if not WEIGHTED_BEST_MODEL_DIR.exists():
        raise FileNotFoundError(
            f"Weighted model not found at {WEIGHTED_BEST_MODEL_DIR}."
        )

    set_seed(RANDOM_SEED)
    device = torch.device("cpu")
    tokenizer = AutoTokenizer.from_pretrained(WEIGHTED_BEST_MODEL_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(
        WEIGHTED_BEST_MODEL_DIR
    )
    model.to(device)

    rows = load_split(TEST_CSV)
    y_true = np.array([row[LABEL_COLUMN] for row in rows], dtype=int)
    y_pred, y_prob = predict_with_proba(model, tokenizer, rows, device)

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
    class_names = [ID2LABEL[i] for i in range(NUM_LABELS)]

    classification_rows = []
    for index in range(NUM_LABELS):
        dataset_label = index + 1
        classification_rows.append(
            {
                "dataset_label": dataset_label,
                "name": ID2LABEL[index],
                "full_name": LABEL_TO_FULL_NAME[dataset_label],
                "precision": float(per_p[index]),
                "recall": float(per_r[index]),
                "f1": float(per_f1[index]),
                "support": int(support[index]),
                "correct": int(cm[index, index]),
                "misclassified": int(support[index] - cm[index, index]),
            }
        )
    classification_rows.append(
        {
            "dataset_label": "",
            "name": "macro",
            "full_name": "Macro average",
            "precision": float(macro_p),
            "recall": float(macro_r),
            "f1": float(macro_f1),
            "support": int(len(rows)),
            "correct": int((y_true == y_pred).sum()),
            "misclassified": int((y_true != y_pred).sum()),
        }
    )

    cm_records = []
    for i, true_name in enumerate(class_names):
        record = {"true_label": true_name}
        for j, pred_name in enumerate(class_names):
            record[f"pred_{pred_name}"] = int(cm[i, j])
        cm_records.append(record)

    pair_counts: Counter[tuple[int, int]] = Counter()
    misclassified: list[dict] = []
    correct: list[dict] = []
    by_true_correct: dict[int, list[dict]] = {i: [] for i in range(NUM_LABELS)}
    by_true_wrong: dict[int, list[dict]] = {i: [] for i in range(NUM_LABELS)}

    for row, true_id, pred_id, probs in zip(rows, y_true, y_pred, y_prob):
        record = example_record(row[TEXT_COLUMN], true_id, pred_id, probs)
        if true_id == pred_id:
            correct.append(record)
            by_true_correct[int(true_id)].append(record)
        else:
            misclassified.append(record)
            by_true_wrong[int(true_id)].append(record)
            pair_counts[(int(true_id) + 1, int(pred_id) + 1)] += 1

    n_errors = len(misclassified)
    pair_rows = []
    for (true_label, pred_label), count in sorted(
        pair_counts.items(),
        key=lambda item: (-item[1], item[0][0], item[0][1]),
    ):
        true_support = int(support[true_label - 1])
        pair_rows.append(
            {
                "true_dataset_label": true_label,
                "true_name": LABEL_TO_NAME[true_label],
                "pred_dataset_label": pred_label,
                "pred_name": LABEL_TO_NAME[pred_label],
                "count": count,
                "percent_of_errors": round(100.0 * count / n_errors, 2) if n_errors else 0.0,
                "percent_of_true_class": (
                    round(100.0 * count / true_support, 2) if true_support else 0.0
                ),
                "confusion_group": confusion_group(true_label, pred_label),
            }
        )

    focused = {
        "lexical_syntactic": 0,
        "syntactic_syntax": 0,
        "semantic_syntax": 0,
        "ambiguous_to_clean": 0,
        "clean_to_ambiguous": 0,
        "other": 0,
    }
    for item in misclassified:
        focused[item["confusion_group"]] += 1

    focused_detail = {
        "lexical_to_syntactic": int(cm[0, 1]),
        "syntactic_to_lexical": int(cm[1, 0]),
        "syntactic_to_syntax": int(cm[1, 3]),
        "syntax_to_syntactic": int(cm[3, 1]),
        "semantic_to_syntax": int(cm[2, 3]),
        "syntax_to_semantic": int(cm[3, 2]),
        "ambiguous_to_clean_by_class": {
            ID2LABEL[i]: int(cm[i, 5]) for i in range(5)
        },
        "clean_to_ambiguous_by_class": {
            ID2LABEL[i]: int(cm[5, i]) for i in range(5)
        },
    }

    correct_examples = []
    misclassified_examples_by_class = []
    for index in range(NUM_LABELS):
        correct_examples.extend(
            pick_examples(by_true_correct[index], EXAMPLES_PER_CLASS)
        )
        misclassified_examples_by_class.extend(
            pick_examples(by_true_wrong[index], EXAMPLES_PER_CLASS)
        )

    ERROR_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(
        ERROR_ANALYSIS_DIR / "confusion_matrix.csv",
        ["true_label"] + [f"pred_{name}" for name in class_names],
        cm_records,
    )
    write_csv(
        ERROR_ANALYSIS_DIR / "classification_report.csv",
        [
            "dataset_label",
            "name",
            "full_name",
            "precision",
            "recall",
            "f1",
            "support",
            "correct",
            "misclassified",
        ],
        classification_rows,
    )
    write_csv(
        ERROR_ANALYSIS_DIR / "confusion_pairs.csv",
        [
            "true_dataset_label",
            "true_name",
            "pred_dataset_label",
            "pred_name",
            "count",
            "percent_of_errors",
            "percent_of_true_class",
            "confusion_group",
        ],
        pair_rows,
    )
    write_csv(
        ERROR_ANALYSIS_DIR / "misclassified_examples.csv",
        [
            "requirement",
            "true_dataset_label",
            "true_name",
            "pred_dataset_label",
            "pred_name",
            "pred_confidence",
            "true_class_probability",
            "confusion_group",
            "token_count",
        ],
        misclassified,
    )
    write_csv(
        ERROR_ANALYSIS_DIR / "correct_examples.csv",
        [
            "requirement",
            "true_dataset_label",
            "true_name",
            "pred_dataset_label",
            "pred_name",
            "pred_confidence",
            "true_class_probability",
            "confusion_group",
            "token_count",
        ],
        correct_examples,
    )
    write_csv(
        ERROR_ANALYSIS_DIR / "misclassified_examples_by_class.csv",
        [
            "requirement",
            "true_dataset_label",
            "true_name",
            "pred_dataset_label",
            "pred_name",
            "pred_confidence",
            "true_class_probability",
            "confusion_group",
            "token_count",
        ],
        misclassified_examples_by_class,
    )

    summary = {
        "model": str(WEIGHTED_BEST_MODEL_DIR),
        "split": str(TEST_CSV),
        "n_rows": len(rows),
        "accuracy": float(accuracy),
        "macro_precision": float(macro_p),
        "macro_recall": float(macro_r),
        "macro_f1": float(macro_f1),
        "n_correct": len(correct),
        "n_misclassified": n_errors,
        "focused_confusion_counts": focused,
        "focused_confusion_detail": focused_detail,
        "hardest_classes_by_f1": [
            {
                "name": row["name"],
                "f1": row["f1"],
                "precision": row["precision"],
                "recall": row["recall"],
                "support": row["support"],
            }
            for row in sorted(
                classification_rows[:-1],
                key=lambda item: item["f1"],
            )
        ],
        "top_confusion_pairs": pair_rows[:10],
    }
    (ERROR_ANALYSIS_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print("Error analysis on untouched test.csv")
    print(f"Model: {WEIGHTED_BEST_MODEL_DIR}")
    print(f"Rows: {len(rows)}")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Macro F1: {macro_f1:.4f}")
    print(f"Correct: {len(correct)}")
    print(f"Misclassified: {n_errors}")
    print("\nPer-class:")
    for row in classification_rows[:-1]:
        print(
            f"  {row['dataset_label']} {row['name']}: "
            f"P={row['precision']:.4f} R={row['recall']:.4f} "
            f"F1={row['f1']:.4f} n={row['support']}"
        )
    print("\nFocused confusion counts:")
    for key, value in focused.items():
        print(f"  {key}: {value}")
    print("\nTop confusion pairs:")
    for pair in pair_rows[:8]:
        print(
            f"  {pair['true_name']} -> {pair['pred_name']}: "
            f"{pair['count']} ({pair['percent_of_errors']}% of errors)"
        )
    print(f"\nArtifacts written under {ERROR_ANALYSIS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
