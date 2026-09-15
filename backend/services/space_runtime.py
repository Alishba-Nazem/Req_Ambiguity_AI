"""Shared inference helpers for the Hugging Face Gradio / ZeroGPU Space.

Reuses AnalyzeService and GenerateService. FastAPI remains the local API.
"""

from __future__ import annotations

import logging
import threading

from pydantic import ValidationError

from backend.config import Settings, get_settings
from backend.schemas import (
    AnalyzeRequest,
    ErrorResponse,
    GenerateRequest,
    HealthResponse,
    RequirementKind,
)
from backend.services.ambiguity_model import (
    ModelUnavailableError,
    TwoStageAmbiguityModel,
    checkpoint_has_weights,
)
from backend.services.analyze import AnalyzeService
from backend.services.generate import GenerateService
from backend.services.rewrite import RewriteService

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_MODEL: TwoStageAmbiguityModel | None = None
_ANALYZE: AnalyzeService | None = None
_GENERATE: GenerateService | None = None
_KINDS = {
    "functional",
    "performance",
    "security",
    "usability",
    "availability",
    "compatibility",
    "other",
}


def reset_runtime() -> None:
    """Test helper. Clears the cached model and services."""
    global _MODEL, _ANALYZE, _GENERATE
    with _LOCK:
        _MODEL = None
        _ANALYZE = None
        _GENERATE = None


def configure_runtime(
    model: TwoStageAmbiguityModel,
    settings: Settings | None = None,
) -> None:
    """Inject a model (including test fakes) without loading checkpoints."""
    global _MODEL, _ANALYZE, _GENERATE
    settings = settings or get_settings()
    with _LOCK:
        _MODEL = model
        _ANALYZE = AnalyzeService(model, RewriteService(settings), settings=settings)
        _GENERATE = GenerateService(_ANALYZE, settings)


def load_space_model(settings: Settings | None = None) -> TwoStageAmbiguityModel:
    """Load both BERT stages once at Space startup.

    Call this at module import in app.py after `import spaces` so ZeroGPU can
    register `.to("cuda")` placements. Do not call this inside `@spaces.GPU`.
    """
    global _MODEL, _ANALYZE, _GENERATE
    settings = settings or get_settings()
    with _LOCK:
        if _MODEL is not None and _ANALYZE is not None and _GENERATE is not None:
            return _MODEL
        model = TwoStageAmbiguityModel.from_disk(settings)
        _MODEL = model
        _ANALYZE = AnalyzeService(model, RewriteService(settings), settings=settings)
        _GENERATE = GenerateService(_ANALYZE, settings)
        return model


def try_load_space_model() -> None:
    """Load checkpoints if present. Gradio still starts when they are missing."""
    try:
        load_space_model()
    except ModelUnavailableError as exc:
        logger.warning("Two-stage checkpoints were not loaded: %s", exc)
    except Exception:
        logger.exception("Failed to load two-stage BERT checkpoints")


def health_payload() -> dict:
    settings = get_settings()
    if _MODEL is not None:
        stage_a = bool(getattr(_MODEL, "stage_a_loaded", True))
        stage_b = bool(getattr(_MODEL, "stage_b_loaded", True))
        loaded = stage_a and stage_b
        error = None
        if not loaded:
            missing = [
                name
                for name, ready in (("Stage A", stage_a), ("Stage B", stage_b))
                if not ready
            ]
            error = (
                f"{' and '.join(missing)} not loaded. Place each inference folder at "
                "ml/outputs_two_stage/stage_a/best_model and "
                "ml/outputs_two_stage/stage_b/best_model."
            )
        return HealthResponse(
            status="ok",
            model_loaded=loaded,
            stage_a_loaded=stage_a,
            stage_b_loaded=stage_b,
            error=error,
        ).model_dump(mode="json")

    stage_a = checkpoint_has_weights(settings.stage_a_dir)
    stage_b = checkpoint_has_weights(settings.stage_b_dir)
    missing = [
        name for name, ready in (("Stage A", stage_a), ("Stage B", stage_b)) if not ready
    ]
    if missing:
        error = (
            f"{' and '.join(missing)} not loaded. Place each inference folder at "
            "ml/outputs_two_stage/stage_a/best_model and "
            "ml/outputs_two_stage/stage_b/best_model "
            "(config.json, tokenizer files, and model.safetensors)."
        )
    else:
        error = (
            "The two-stage model is not loaded yet. Restart the Space after the "
            "inference folders are uploaded."
        )
    return HealthResponse(
        status="ok",
        model_loaded=False,
        stage_a_loaded=stage_a,
        stage_b_loaded=stage_b,
        error=error,
    ).model_dump(mode="json")


def analyze_payload(requirement: str) -> dict:
    try:
        text = AnalyzeRequest(requirement=requirement).requirement
        return _require_analyze().analyze(text).model_dump(mode="json")
    except ValidationError as exc:
        return _validation_error(exc, "requirement")
    except ModelUnavailableError as exc:
        return ErrorResponse(error=str(exc), code="model_unavailable").model_dump()
    except Exception:
        logger.exception("Gradio analyze failed")
        return ErrorResponse(
            error="Inference failed while classifying the requirement.",
            code="model_unavailable",
        ).model_dump()


def generate_payload(
    idea: str,
    requirement_type: str | None = None,
    details: str | None = None,
) -> dict:
    try:
        payload = GenerateRequest(
            idea=idea,
            requirement_type=_parse_kind(requirement_type),
            details=(details or "").strip() or None,
        )
        return _require_generate().generate(
            payload.idea, payload.requirement_type, payload.details
        ).model_dump(mode="json")
    except ValidationError as exc:
        return _validation_error(exc, "idea")
    except ModelUnavailableError as exc:
        return ErrorResponse(error=str(exc), code="model_unavailable").model_dump()
    except Exception:
        logger.exception("Gradio generate failed")
        return ErrorResponse(
            error="The requirement could not be generated right now.",
            code="model_unavailable",
        ).model_dump()


def _require_analyze() -> AnalyzeService:
    if _ANALYZE is None:
        raise ModelUnavailableError(
            "The two-stage model is not loaded. Upload "
            "ml/outputs_two_stage/stage_a/best_model and "
            "ml/outputs_two_stage/stage_b/best_model, then restart the Space."
        )
    return _ANALYZE


def _require_generate() -> GenerateService:
    if _GENERATE is None:
        raise ModelUnavailableError(
            "The two-stage model is not loaded. Upload "
            "ml/outputs_two_stage/stage_a/best_model and "
            "ml/outputs_two_stage/stage_b/best_model, then restart the Space."
        )
    return _GENERATE


def _parse_kind(value: str | None) -> RequirementKind | None:
    text = (value or "").strip().lower()
    if not text or text in {"auto", "let the assistant choose"}:
        return None
    if text not in _KINDS:
        return None
    return text  # type: ignore[return-value]


def _validation_error(exc: ValidationError, field: str) -> dict:
    message = "Invalid request."
    for item in exc.errors():
        loc = [str(part) for part in item.get("loc", ()) if part != "body"]
        raw = str(item.get("msg") or message)
        if field in loc or not loc:
            message = raw[len("Value error, ") :] if raw.startswith("Value error, ") else raw
            break
        if raw.startswith("Value error, "):
            message = raw[len("Value error, "):]
            break
    return ErrorResponse(error=message, code="validation_error").model_dump()
