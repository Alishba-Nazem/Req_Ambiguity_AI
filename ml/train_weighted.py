"""BERT baseline, experiment 2: class-weighted loss.

Same data, split, seed, tokenizer, and hyperparameters as ml/train.py.
The only change is the training objective: CrossEntropyLoss is weighted
inversely to class frequency so the model is penalized more for missing
minority ambiguity classes (lexical, syntactic, semantic, syntax) instead
of defaulting to the majority "clean" class.

Results are saved to a separate directory (ml/outputs_weighted/) so the
original unweighted baseline in ml/outputs/ is preserved for comparison.
"""

from __future__ import annotations

import json
from collections import Counter

import numpy as np
import torch
import torch.nn as nn
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

from config import (
    BATCH_SIZE,
    ID2LABEL,
    LABEL_COLUMN,
    LEARNING_RATE,
    MAX_LENGTH,
    MODEL_NAME,
    NUM_EPOCHS,
    NUM_LABELS,
    RANDOM_SEED,
    TEXT_COLUMN,
    TRAIN_CSV,
    VALIDATION_CSV,
    WEIGHTED_BEST_MODEL_DIR,
    WEIGHTED_OUTPUT_DIR,
)
from train import (
    RequirementDataset,
    compute_metrics,
    find_latest_checkpoint,
    load_split,
    resolve_model_source,
    set_seed,
    use_local_files,
)


def compute_class_weights(labels: list[int]) -> torch.Tensor:
    """Inverse-frequency weights, normalized so the mean weight is 1.0."""
    counts = Counter(labels)
    total = len(labels)
    weights = [
        total / (NUM_LABELS * counts.get(class_id, 1))
        for class_id in range(NUM_LABELS)
    ]
    weights_tensor = torch.tensor(weights, dtype=torch.float)
    weights_tensor = weights_tensor / weights_tensor.mean()
    return weights_tensor


class WeightedLossTrainer(Trainer):
    def __init__(self, *args, class_weights: torch.Tensor, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        loss_fct = nn.CrossEntropyLoss(
            weight=self.class_weights.to(logits.device)
        )
        loss = loss_fct(logits.view(-1, NUM_LABELS), labels.view(-1))
        return (loss, outputs) if return_outputs else loss


def main() -> None:
    set_seed(RANDOM_SEED)

    print("Requirement Ambiguity AI — BERT baseline (class-weighted loss)")
    print(f"Model: {MODEL_NAME}")
    print(f"Seed: {RANDOM_SEED}")

    train_rows = load_split(TRAIN_CSV)
    validation_rows = load_split(VALIDATION_CSV)

    print(f"Training rows: {len(train_rows)}")
    print(f"Validation rows: {len(validation_rows)}")

    train_labels = [row[LABEL_COLUMN] for row in train_rows]
    train_counts = Counter(train_labels)

    print("\nTraining label distribution:")
    for label_id in sorted(ID2LABEL):
        dataset_label = label_id + 1
        print(
            f"  {dataset_label} ({ID2LABEL[label_id]}): "
            f"{train_counts.get(label_id, 0)}"
        )

    class_weights = compute_class_weights(train_labels)
    print("\nClass weights (inverse frequency, mean-normalized):")
    for label_id in sorted(ID2LABEL):
        dataset_label = label_id + 1
        print(f"  {dataset_label} ({ID2LABEL[label_id]}): {class_weights[label_id]:.4f}")

    model_source = resolve_model_source()
    print(f"\nModel source: {model_source}")

    tokenizer = AutoTokenizer.from_pretrained(
        model_source,
        local_files_only=use_local_files(model_source),
    )

    train_texts = [row[TEXT_COLUMN] for row in train_rows]
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

    train_dataset = RequirementDataset(train_encodings, train_labels)
    validation_dataset = RequirementDataset(validation_encodings, validation_labels)

    model = AutoModelForSequenceClassification.from_pretrained(
        model_source,
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id={name: index for index, name in ID2LABEL.items()},
        local_files_only=use_local_files(model_source),
    )

    WEIGHTED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(WEIGHTED_OUTPUT_DIR),
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

    trainer = WeightedLossTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        compute_metrics=compute_metrics,
        class_weights=class_weights,
    )

    resume_checkpoint = find_latest_checkpoint(WEIGHTED_OUTPUT_DIR)
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

    WEIGHTED_BEST_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(WEIGHTED_BEST_MODEL_DIR))
    tokenizer.save_pretrained(str(WEIGHTED_BEST_MODEL_DIR))

    history_path = WEIGHTED_OUTPUT_DIR / "train_log_history.json"
    history_path.write_text(
        json.dumps(trainer.state.log_history, indent=2),
        encoding="utf-8",
    )

    metrics_path = WEIGHTED_OUTPUT_DIR / "validation_metrics.json"
    serializable = {
        key: (float(value) if isinstance(value, (float, np.floating)) else value)
        for key, value in metrics.items()
    }
    metrics_path.write_text(
        json.dumps(serializable, indent=2),
        encoding="utf-8",
    )

    print(f"\nBest model saved to: {WEIGHTED_BEST_MODEL_DIR}")
    print("Test.csv was not used during training or model selection.")


if __name__ == "__main__":
    main()
