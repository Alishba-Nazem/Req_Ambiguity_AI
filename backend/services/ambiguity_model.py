"""Two-stage BERT inference. Models are loaded once and kept in memory."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from backend.config import Settings, get_settings
from backend.schemas import AmbiguityType, Classification
from ml.config import STAGE_A_ID2LABEL, STAGE_B_ID2LABEL


class ModelUnavailableError(Exception):
    """Raised when trained checkpoints are missing or cannot be loaded."""


@dataclass(frozen=True)
class ModelPrediction:
    classification: Classification
    ambiguity_type: AmbiguityType | None
    ambiguity_score: int
    confidence: float
    stage_a_confidence: float | None = None
    stage_b_confidence: float | None = None


def ambiguity_score_from_probability(ambiguous_probability: float) -> int:
    """Integer 0-100 from Stage A P(ambiguous). Higher means more ambiguous."""
    score = int(round(float(ambiguous_probability) * 100))
    return max(0, min(100, score))


def checkpoint_has_weights(path: Path) -> bool:
    return (path / "model.safetensors").exists() or (path / "pytorch_model.bin").exists()


def _label_name(id2label: dict, index: int) -> str:
    if index in id2label:
        return str(id2label[index])
    return str(id2label[str(index)])


class TwoStageAmbiguityModel:
    """Stage A: clean vs ambiguous. Stage B: type, only if Stage A is ambiguous."""

    def __init__(
        self,
        stage_a,
        tokenizer_a,
        stage_b,
        tokenizer_b,
        device: torch.device,
        max_length: int,
        stage_a_id2label: dict | None = None,
        stage_b_id2label: dict | None = None,
    ) -> None:
        self._stage_a = stage_a
        self._tokenizer_a = tokenizer_a
        self._stage_b = stage_b
        self._tokenizer_b = tokenizer_b
        self._device = device
        self._max_length = max_length
        self._stage_a_id2label = stage_a_id2label or dict(STAGE_A_ID2LABEL)
        self._stage_b_id2label = stage_b_id2label or dict(STAGE_B_ID2LABEL)
        self._lock = threading.Lock()
        self.loaded = True

    @classmethod
    def from_disk(cls, settings: Settings | None = None) -> TwoStageAmbiguityModel:
        settings = settings or get_settings()
        stage_a_dir = settings.stage_a_dir
        stage_b_dir = settings.stage_b_dir

        for path, name in ((stage_a_dir, "Stage A"), (stage_b_dir, "Stage B")):
            if not path.is_dir():
                raise ModelUnavailableError(
                    f"{name} checkpoint not found at {path}. "
                    "Copy trained artifacts into ml/outputs_two_stage/."
                )
            if not checkpoint_has_weights(path):
                raise ModelUnavailableError(
                    f"{name} weights are missing in {path} "
                    "(expected model.safetensors). Training was not run from this API."
                )

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        tokenizer_a = AutoTokenizer.from_pretrained(stage_a_dir, local_files_only=True)
        tokenizer_b = AutoTokenizer.from_pretrained(stage_b_dir, local_files_only=True)
        stage_a = AutoModelForSequenceClassification.from_pretrained(
            stage_a_dir,
            local_files_only=True,
        ).to(device)
        stage_b = AutoModelForSequenceClassification.from_pretrained(
            stage_b_dir,
            local_files_only=True,
        ).to(device)
        stage_a.eval()
        stage_b.eval()

        stage_a_id2label = {
            int(key): value for key, value in stage_a.config.id2label.items()
        }
        stage_b_id2label = {
            int(key): value for key, value in stage_b.config.id2label.items()
        }

        return cls(
            stage_a=stage_a,
            tokenizer_a=tokenizer_a,
            stage_b=stage_b,
            tokenizer_b=tokenizer_b,
            device=device,
            max_length=settings.max_length,
            stage_a_id2label=stage_a_id2label,
            stage_b_id2label=stage_b_id2label,
        )

    def _probabilities(self, model, tokenizer, text: str) -> torch.Tensor:
        encoded = tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=self._max_length,
            return_tensors="pt",
        )
        encoded = {key: value.to(self._device) for key, value in encoded.items()}
        with torch.no_grad():
            logits = model(**encoded).logits
        return torch.softmax(logits, dim=-1)[0]

    def predict(self, requirement: str) -> ModelPrediction:
        try:
            with self._lock:
                stage_a_probs = self._probabilities(
                    self._stage_a,
                    self._tokenizer_a,
                    requirement,
                )
                stage_a_index = int(torch.argmax(stage_a_probs).item())
                p_ambiguous = float(stage_a_probs[1].item())
                score = ambiguity_score_from_probability(p_ambiguous)
                stage_a_label = _label_name(self._stage_a_id2label, stage_a_index)

                stage_a_confidence = round(float(stage_a_probs[stage_a_index].item()), 4)
                if stage_a_label == "clean":
                    return ModelPrediction(
                        classification="clean",
                        ambiguity_type=None,
                        ambiguity_score=score,
                        confidence=stage_a_confidence,
                        stage_a_confidence=stage_a_confidence,
                        stage_b_confidence=None,
                    )

                stage_b_probs = self._probabilities(
                    self._stage_b,
                    self._tokenizer_b,
                    requirement,
                )
                stage_b_index = int(torch.argmax(stage_b_probs).item())
                ambiguity_type = _label_name(self._stage_b_id2label, stage_b_index)
                if ambiguity_type not in (
                    "lexical",
                    "syntactic",
                    "semantic",
                    "syntax",
                    "pragmatic",
                ):
                    raise ModelUnavailableError("Stage B returned an unknown label.")
                stage_b_confidence = round(float(stage_b_probs[stage_b_index].item()), 4)
                return ModelPrediction(
                    classification="ambiguous",
                    ambiguity_type=ambiguity_type,
                    ambiguity_score=score,
                    confidence=stage_a_confidence,
                    stage_a_confidence=stage_a_confidence,
                    stage_b_confidence=stage_b_confidence,
                )
        except ModelUnavailableError:
            raise
        except Exception as exc:
            raise ModelUnavailableError(
                "Inference failed while classifying the requirement."
            ) from exc
