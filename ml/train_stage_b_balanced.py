"""Train Stage B on the curated short-example augmentation.

This experiment changes only the Stage B training rows. It uses ordinary
cross-entropy and writes a separate checkpoint.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments

ML_DIR = Path(__file__).resolve().parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from config import (  # noqa: E402
    BATCH_SIZE,
    LEARNING_RATE,
    MAX_LENGTH,
    NUM_EPOCHS,
    RANDOM_SEED,
    STAGE_B_BEST_MODEL_DIR,
    STAGE_B_ID2LABEL,
    STAGE_B_LABEL2ID,
    STAGE_B_NUM_LABELS,
    TEST_CSV,
    TEXT_COLUMN,
    VALIDATION_CSV,
)
from prepare_stage_b_balanced import OUTPUT_DIR as DATA_DIR, read_csv  # noqa: E402
from train import RequirementDataset, compute_metrics, resolve_model_source, set_seed, use_local_files  # noqa: E402
from train_stage_b_weighted import _evaluate_model, _print_fragment_metrics, _print_metrics  # noqa: E402
from train_two_stage import load_raw_rows, to_stage_b  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs_two_stage" / "stage_b_balanced"
BEST_MODEL_DIR = OUTPUT_DIR / "best_model"


def dataset(
    rows: list[dict[str, str]],
    tokenizer,
    labels_are_dataset_ids: bool = True,
) -> RequirementDataset:
    encoded = tokenizer(
        [row[TEXT_COLUMN] for row in rows],
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
    )
    labels = [int(row["label"]) for row in rows]
    if labels_are_dataset_ids:
        labels = [label - 1 for label in labels]
    return RequirementDataset(encoded, labels)


def train(output_dir: Path = OUTPUT_DIR, best_model_dir: Path = BEST_MODEL_DIR) -> None:
    set_seed(RANDOM_SEED)
    train_rows = read_csv(DATA_DIR / "train.csv")
    validation_rows = to_stage_b(load_raw_rows(VALIDATION_CSV))
    model_source = resolve_model_source()
    tokenizer = AutoTokenizer.from_pretrained(model_source, local_files_only=use_local_files(model_source))
    model = AutoModelForSequenceClassification.from_pretrained(
        model_source,
        num_labels=STAGE_B_NUM_LABELS,
        id2label=STAGE_B_ID2LABEL,
        label2id=STAGE_B_LABEL2ID,
        local_files_only=use_local_files(model_source),
    )
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
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=dataset(train_rows, tokenizer),
        eval_dataset=dataset(validation_rows, tokenizer, labels_are_dataset_ids=False),
        compute_metrics=compute_metrics,
    )
    print(f"Training rows: {len(train_rows)}")
    print(f"Validation rows: {len(validation_rows)}")
    print(f"Output: {best_model_dir}")
    trainer.train()
    best_model_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(best_model_dir))
    tokenizer.save_pretrained(str(best_model_dir))
    validation_metrics = _evaluate_model(trainer.model, tokenizer, validation_rows, torch.device("cpu"))
    test_rows = to_stage_b(load_raw_rows(TEST_CSV))
    test_metrics = _evaluate_model(trainer.model, tokenizer, test_rows, torch.device("cpu"))
    _print_metrics("validation", validation_metrics)
    _print_metrics("test", test_metrics)
    _print_fragment_metrics(test_rows, test_metrics.pop("predicted"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--best-model-dir", type=Path, default=BEST_MODEL_DIR)
    args = parser.parse_args()
    train(args.output_dir, args.best_model_dir)
