"""Two-stage BERT experiment.

Stage A: binary clean vs ambiguous on the full train/validation splits.
Stage B: 5-way ambiguity type on ambiguous rows only.

Dataset CSVs are not modified. Test.csv is not used for training or
checkpoint selection. Outputs go to ml/outputs_two_stage/.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

from config import (
    BATCH_SIZE,
    LABEL_COLUMN,
    LABEL_TO_NAME,
    LEARNING_RATE,
    MAX_LENGTH,
    MODEL_NAME,
    NUM_EPOCHS,
    RANDOM_SEED,
    STAGE_A_BEST_MODEL_DIR,
    STAGE_A_ID2LABEL,
    STAGE_A_LABEL2ID,
    STAGE_A_NUM_LABELS,
    STAGE_A_OUTPUT_DIR,
    STAGE_B_BEST_MODEL_DIR,
    STAGE_B_ID2LABEL,
    STAGE_B_LABEL2ID,
    STAGE_B_NUM_LABELS,
    STAGE_B_OUTPUT_DIR,
    TEXT_COLUMN,
    TRAIN_CSV,
    TWO_STAGE_OUTPUT_DIR,
    VALIDATION_CSV,
)
from train import (
    RequirementDataset,
    compute_metrics,
    find_latest_checkpoint,
    resolve_model_source,
    set_seed,
)


def load_raw_rows(csv_path: Path) -> list[dict]:
    """Load requirement text and original dataset labels 1-6."""
    rows = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != [TEXT_COLUMN, LABEL_COLUMN]:
            raise ValueError(
                f"Unexpected columns in {csv_path}: {reader.fieldnames}"
            )
        for row in reader:
            label = int(row[LABEL_COLUMN])
            if label not in LABEL_TO_NAME:
                raise ValueError(f"Invalid label {label} in {csv_path}")
            rows.append(
                {
                    TEXT_COLUMN: row[TEXT_COLUMN],
                    "dataset_label": label,
                }
            )
    return rows


def to_stage_a(rows: list[dict]) -> list[dict]:
    """Map dataset labels: 6 -> 0 (clean), 1-5 -> 1 (ambiguous)."""
    converted = []
    for row in rows:
        converted.append(
            {
                TEXT_COLUMN: row[TEXT_COLUMN],
                LABEL_COLUMN: 0 if row["dataset_label"] == 6 else 1,
                "dataset_label": row["dataset_label"],
            }
        )
    return converted


def to_stage_b(rows: list[dict]) -> list[dict]:
    """Keep labels 1-5 only and map them to 0-4. Drop clean (6)."""
    converted = []
    for row in rows:
        dataset_label = row["dataset_label"]
        if dataset_label == 6:
            continue
        converted.append(
            {
                TEXT_COLUMN: row[TEXT_COLUMN],
                LABEL_COLUMN: dataset_label - 1,
                "dataset_label": dataset_label,
            }
        )
    return converted


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def serialize_metrics(metrics: dict) -> dict:
    return {
        key: (float(value) if isinstance(value, (float, np.floating)) else value)
        for key, value in metrics.items()
    }


def train_stage(
    stage_name: str,
    train_rows: list[dict],
    validation_rows: list[dict],
    output_dir: Path,
    best_model_dir: Path,
    num_labels: int,
    id2label: dict[int, str],
    label2id: dict[str, int],
) -> dict:
    print(f"\n===== {stage_name} =====")
    print(f"Training rows: {len(train_rows)}")
    print(f"Validation rows: {len(validation_rows)}")

    train_counts = Counter(row[LABEL_COLUMN] for row in train_rows)
    print("Training label distribution (stage indices):")
    for index in sorted(id2label):
        print(f"  {index} ({id2label[index]}): {train_counts.get(index, 0)}")

    model_source = resolve_model_source()
    print(f"Model source: {model_source}")

    tokenizer = AutoTokenizer.from_pretrained(model_source, local_files_only=True)
    train_encodings = tokenizer(
        [row[TEXT_COLUMN] for row in train_rows],
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
    )
    validation_encodings = tokenizer(
        [row[TEXT_COLUMN] for row in validation_rows],
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
    )

    train_dataset = RequirementDataset(
        train_encodings,
        [row[LABEL_COLUMN] for row in train_rows],
    )
    validation_dataset = RequirementDataset(
        validation_encodings,
        [row[LABEL_COLUMN] for row in validation_rows],
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        model_source,
        num_labels=num_labels,
        id2label=id2label,
        label2id=label2id,
        local_files_only=True,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(
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

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        compute_metrics=compute_metrics,
    )

    resume_checkpoint = find_latest_checkpoint(output_dir)
    if resume_checkpoint:
        print(f"Resuming {stage_name} from checkpoint: {resume_checkpoint}")
    else:
        print(f"Starting {stage_name} training...")
    trainer.train(resume_from_checkpoint=resume_checkpoint)

    print(f"\n{stage_name} validation results (used for checkpoint selection):")
    metrics = trainer.evaluate()
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")

    best_model_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(best_model_dir))
    tokenizer.save_pretrained(str(best_model_dir))

    write_json(output_dir / "train_log_history.json", trainer.state.log_history)
    write_json(output_dir / "validation_metrics.json", serialize_metrics(metrics))
    print(f"Best {stage_name} model saved to: {best_model_dir}")
    return serialize_metrics(metrics)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train the two-stage BERT experiment."
    )
    parser.add_argument(
        "--stage",
        choices=("a", "b", "both"),
        default="both",
        help="Train Stage A, Stage B, or both (default).",
    )
    args = parser.parse_args()

    set_seed(RANDOM_SEED)
    TWO_STAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Requirement Ambiguity AI — two-stage BERT")
    print(f"Model: {MODEL_NAME}")
    print(f"Seed: {RANDOM_SEED}")
    print("Label mapping:")
    print("  Stage A: dataset 6 -> 0 clean; dataset 1-5 -> 1 ambiguous")
    print("  Stage B: dataset 1-5 -> 0-4; dataset 6 excluded")

    raw_train = load_raw_rows(TRAIN_CSV)
    raw_val = load_raw_rows(VALIDATION_CSV)

    if args.stage in ("a", "both"):
        train_stage(
            "Stage A",
            to_stage_a(raw_train),
            to_stage_a(raw_val),
            STAGE_A_OUTPUT_DIR,
            STAGE_A_BEST_MODEL_DIR,
            STAGE_A_NUM_LABELS,
            STAGE_A_ID2LABEL,
            STAGE_A_LABEL2ID,
        )

    if args.stage in ("b", "both"):
        train_stage(
            "Stage B",
            to_stage_b(raw_train),
            to_stage_b(raw_val),
            STAGE_B_OUTPUT_DIR,
            STAGE_B_BEST_MODEL_DIR,
            STAGE_B_NUM_LABELS,
            STAGE_B_ID2LABEL,
            STAGE_B_LABEL2ID,
        )

    print("\nTest.csv was not used during training or model selection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
