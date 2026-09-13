from pathlib import Path
from unittest.mock import MagicMock

import pytest
import torch

from backend.config import Settings
from backend.services.ambiguity_model import (
    ModelUnavailableError,
    TwoStageAmbiguityModel,
    ambiguity_score_from_probability,
    checkpoint_has_weights,
)


def test_ambiguity_score_from_probability():
    assert ambiguity_score_from_probability(0.0) == 0
    assert ambiguity_score_from_probability(1.0) == 100
    assert ambiguity_score_from_probability(0.781) == 78
    assert ambiguity_score_from_probability(-0.2) == 0
    assert ambiguity_score_from_probability(1.7) == 100


def test_checkpoint_has_weights(tmp_path: Path):
    missing = tmp_path / "empty"
    missing.mkdir()
    assert checkpoint_has_weights(missing) is False
    (missing / "model.safetensors").write_bytes(b"x")
    assert checkpoint_has_weights(missing) is True


def test_from_disk_missing_directories(tmp_path: Path):
    settings = Settings(model_dir=tmp_path)
    with pytest.raises(ModelUnavailableError, match="Stage A"):
        TwoStageAmbiguityModel.from_disk(settings)


def test_from_disk_missing_weights(tmp_path: Path):
    stage_a = tmp_path / "stage_a" / "best_model"
    stage_b = tmp_path / "stage_b" / "best_model"
    stage_a.mkdir(parents=True)
    stage_b.mkdir(parents=True)
    settings = Settings(model_dir=tmp_path)
    with pytest.raises(ModelUnavailableError, match="weights"):
        TwoStageAmbiguityModel.from_disk(settings)


def _model_with_mocked_forward() -> TwoStageAmbiguityModel:
    return TwoStageAmbiguityModel(
        stage_a=MagicMock(),
        tokenizer_a=MagicMock(),
        stage_b=MagicMock(),
        tokenizer_b=MagicMock(),
        device=torch.device("cpu"),
        max_length=128,
    )


def test_predict_clean_skips_stage_b():
    model = _model_with_mocked_forward()
    model._probabilities = MagicMock(return_value=torch.tensor([0.92, 0.08]))
    prediction = model.predict("The system shall lock the account after 5 failed login attempts.")
    assert prediction.classification == "clean"
    assert prediction.ambiguity_type is None
    assert prediction.ambiguity_score == 8
    assert prediction.confidence == 0.92
    assert model._probabilities.call_count == 1


def test_predict_ambiguous_runs_stage_b():
    model = _model_with_mocked_forward()
    model._probabilities = MagicMock(
        side_effect=[
            torch.tensor([0.22, 0.78]),
            torch.tensor([0.05, 0.04, 0.06, 0.04, 0.81]),
        ]
    )
    prediction = model.predict("The system should respond quickly.")
    assert prediction.classification == "ambiguous"
    assert prediction.ambiguity_type == "pragmatic"
    assert prediction.ambiguity_score == 78
    assert prediction.confidence == 0.78
    assert prediction.stage_a_confidence == 0.78
    assert prediction.stage_b_confidence == 0.81
    assert model._probabilities.call_count == 2
