from fastapi.testclient import TestClient

from backend.main import create_app
from backend.services.ambiguity_model import ModelPrediction
from backend.tests.fakes import FakeModel, FakeRewriteService


def _client(prediction: ModelPrediction | None = None) -> TestClient:
    model = None
    if prediction is not None:
        model = FakeModel(prediction)
    app = create_app(
        model=model,
        rewrite_service=FakeRewriteService(),
        load_model=False,
    )
    return TestClient(app)


def test_health_ok_without_model():
    client = _client()
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is False
    assert body["stage_a_loaded"] is False
    assert body["stage_b_loaded"] is False
    assert "error" in body


def test_health_ok_with_model():
    client = _client(
        ModelPrediction(
            classification="clean",
            ambiguity_type=None,
            ambiguity_score=8,
            confidence=0.94,
        )
    )
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["model_loaded"] is True
    assert response.json()["stage_a_loaded"] is True
    assert response.json()["stage_b_loaded"] is True
    assert response.json()["error"] is None
