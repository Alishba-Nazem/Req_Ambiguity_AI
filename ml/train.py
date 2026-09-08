from __future__ import annotations

import csv
import json
import os
import random
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

from config import (
    BATCH_SIZE,
    BEST_MODEL_DIR,
    ID2LABEL,
    LABEL_COLUMN,
    LABEL_TO_NAME,
    LEARNING_RATE,
    MAX_LENGTH,
    MODEL_NAME,
    NUM_EPOCHS,
    NUM_LABELS,
    OUTPUT_DIR,
    RANDOM_SEED,
    TEXT_COLUMN,
    TRAIN_CSV,
    VALIDATION_CSV,
)


def find_latest_checkpoint(output_dir: Path) -> str | None:
    """Resume from the highest-step checkpoint under output_dir, if any."""
    if not output_dir.exists():
        return None

    checkpoints = []
    for entry in output_dir.iterdir():
        if entry.is_dir() and entry.name.startswith("checkpoint-"):
            try:
                step = int(entry.name.split("-")[-1])
            except ValueError:
                continue
            checkpoints.append((step, entry))

    if not checkpoints:
        return None

    checkpoints.sort(key=lambda pair: pair[0])
    return str(checkpoints[-1][1])


def resolve_model_source() -> str:
    """Prefer a complete local snapshot so training does not wait on the Hub."""
    local = (
        Path.home()
        / ".cache"
        / "huggingface"
        / "hub"
        / "models--google-bert--bert-base-uncased"
        / "snapshots"
        / "86b5e0934494bd15c9632b12f734a8a67f723594"
    )
    if (local / "model.safetensors").exists() and (local / "config.json").exists():
        return str(local)
    return MODEL_NAME


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_split(csv_path: Path) -> list[dict]:
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
                    LABEL_COLUMN: label - 1,
                }
            )

    return rows


def compute_metrics(eval_prediction):
    if hasattr(eval_prediction, "predictions"):
        logits = eval_prediction.predictions
        labels = eval_prediction.label_ids
    else:
        logits, labels = eval_prediction

    if isinstance(logits, (tuple, list)):
        logits = logits[0]

    predictions = np.argmax(logits, axis=-1)

    precision, recall, f1, _ = precision_recall_fscore_support(
        labels,
        predictions,
        average="macro",
        zero_division=0,
    )

    accuracy = accuracy_score(labels, predictions)

    return {
        "accuracy": accuracy,
        "macro_precision": precision,
        "macro_recall": recall,
        "macro_f1": f1,
    }


class RequirementDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, index):
        item = {
            key: torch.tensor(value[index])
            for key, value in self.encodings.items()
        }
        item["labels"] = torch.tensor(self.labels[index], dtype=torch.long)
        return item


def main() -> None:
    set_seed(RANDOM_SEED)

    print("Requirement Ambiguity AI — BERT baseline")
    print(f"Model: {MODEL_NAME}")
    print(f"Seed: {RANDOM_SEED}")

    train_rows = load_split(TRAIN_CSV)
    validation_rows = load_split(VALIDATION_CSV)

    print(f"Training rows: {len(train_rows)}")
    print(f"Validation rows: {len(validation_rows)}")

    print("\nTraining label distribution:")
    train_counts = Counter(row[LABEL_COLUMN] for row in train_rows)

    for label_id in sorted(ID2LABEL):
        dataset_label = label_id + 1
        print(
            f"  {dataset_label} ({ID2LABEL[label_id]}): "
            f"{train_counts.get(label_id, 0)}"
        )

    model_source = resolve_model_source()
    print(f"Model source: {model_source}")

    tokenizer = AutoTokenizer.from_pretrained(model_source, local_files_only=True)

    train_texts = [row[TEXT_COLUMN] for row in train_rows]
    train_labels = [row[LABEL_COLUMN] for row in train_rows]

    validation_texts = [row[TEXT_COLUMN] for row in validation_rows]
    validation_labels = [row[LABEL_COLUMN] for row in validation_rows]

    train_encodings = tokenizer(
        train_texts,
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
    )

    validation_encodings = tokenizer(
        validation_texts,
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
    )

    train_dataset = RequirementDataset(
        train_encodings,
        train_labels,
    )

    validation_dataset = RequirementDataset(
        validation_encodings,
        validation_labels,
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        model_source,
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id={name: index for index, name in ID2LABEL.items()},
        local_files_only=True,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
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

    resume_checkpoint = find_latest_checkpoint(OUTPUT_DIR)
    if resume_checkpoint:
        print(f"\nResuming training from checkpoint: {resume_checkpoint}")
    else:
        print("\nStarting training...")
    trainer.train(resume_from_checkpoint=resume_checkpoint)

    print("\nFinal validation results:")
    metrics = trainer.evaluate()

    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")

    BEST_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(BEST_MODEL_DIR))
    tokenizer.save_pretrained(str(BEST_MODEL_DIR))

    history_path = OUTPUT_DIR / "train_log_history.json"
    history_path.write_text(
        json.dumps(trainer.state.log_history, indent=2),
        encoding="utf-8",
    )

    metrics_path = OUTPUT_DIR / "validation_metrics.json"
    serializable = {
        key: (float(value) if isinstance(value, (float, np.floating)) else value)
        for key, value in metrics.items()
    }
    metrics_path.write_text(
        json.dumps(serializable, indent=2),
        encoding="utf-8",
    )

    print(f"\nBest model saved to: {BEST_MODEL_DIR}")
    print("Test.csv was not used during training or model selection.")


if __name__ == "__main__":
    main()