from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import Settings, get_settings
from backend.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
)
from backend.services.ambiguity_model import (
    ModelUnavailableError,
    TwoStageAmbiguityModel,
    checkpoint_has_weights,
)
from backend.services.analyze import AnalyzeService
from backend.services.generate import GenerateService
from backend.services.llm_analyzer import LlmAnalyzer
from backend.services.rewrite import RewriteService

logger = logging.getLogger(__name__)


class ClientError(Exception):
    def __init__(self, message: str, status_code: int = 422, code: str = "validation_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _error(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=message, code=code).model_dump(),
    )


def _stage_load_flags(model: object | None) -> tuple[bool, bool]:
    if model is None:
        return False, False
    stage_a = getattr(model, "stage_a_loaded", None)
    stage_b = getattr(model, "stage_b_loaded", None)
    if isinstance(stage_a, bool) and isinstance(stage_b, bool):
        return stage_a, stage_b
    return True, True


def _checkpoint_status_error(settings: Settings) -> str:
    missing: list[str] = []
    if not checkpoint_has_weights(settings.stage_a_dir):
        missing.append("Stage A")
    if not checkpoint_has_weights(settings.stage_b_dir):
        missing.append("Stage B")
    if missing:
        return (
            f"{' and '.join(missing)} not loaded. Place each inference folder at "
            "ml/outputs_two_stage/stage_a/best_model and "
            "ml/outputs_two_stage/stage_b/best_model "
            "(config.json, tokenizer files, and model.safetensors)."
        )
    return "The two-stage model failed to load."


def create_app(
    settings: Settings | None = None,
    model: TwoStageAmbiguityModel | None = None,
    rewrite_service: RewriteService | None = None,
    llm_analyzer: LlmAnalyzer | None = None,
    load_model: bool = True,
) -> FastAPI:
    settings = settings or get_settings()
    rewrite = rewrite_service or RewriteService(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if getattr(app.state, "model", None) is None and load_model:
            try:
                app.state.model = TwoStageAmbiguityModel.from_disk(settings)
                app.state.model_error = None
            except Exception:
                logger.exception("Failed to load two-stage BERT checkpoints")
                app.state.model = None
                app.state.model_error = _checkpoint_status_error(settings)
        yield

    app = FastAPI(
        title="Requirement Ambiguity AI",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.rewrite_service = rewrite
    app.state.llm_analyzer = llm_analyzer
    app.state.model = model
    if model is not None:
        app.state.model_error = None
    elif load_model:
        app.state.model_error = _checkpoint_status_error(settings)
    else:
        app.state.model_error = "Model was not loaded."
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        message = _validation_message(exc.errors())
        return _error(422, message, "validation_error")

    @app.exception_handler(ClientError)
    async def client_handler(_request: Request, exc: ClientError) -> JSONResponse:
        return _error(exc.status_code, exc.message, exc.code)

    @app.exception_handler(ModelUnavailableError)
    async def model_handler(
        _request: Request,
        exc: ModelUnavailableError,
    ) -> JSONResponse:
        return _error(503, str(exc), "model_unavailable")

    @app.get("/api/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        model = getattr(request.app.state, "model", None)
        loaded = model is not None
        stage_a, stage_b = _stage_load_flags(model)
        return HealthResponse(
            status="ok",
            model_loaded=loaded,
            stage_a_loaded=stage_a,
            stage_b_loaded=stage_b,
            error=None if loaded else getattr(request.app.state, "model_error", None),
        )

    @app.post(
        "/api/analyze",
        response_model=AnalyzeResponse,
        summary="Analyze a requirement",
        description=(
            "Returns fused hybrid analysis. Canonical fields are "
            "final_assessment, ml_prediction.stage_a, ml_prediction.stage_b, "
            "linguistic_findings, llm_analysis, and issues. "
            "Top-level classification/confidence/ambiguity_score are BERT-only "
            "and are not the fused score."
        ),
    )
    def analyze(payload: AnalyzeRequest, request: Request) -> AnalyzeResponse:
        settings_local: Settings = request.app.state.settings
        if len(payload.requirement) > settings_local.max_requirement_chars:
            raise ClientError(
                "requirement must be at most "
                f"{settings_local.max_requirement_chars} characters"
            )

        loaded_model = getattr(request.app.state, "model", None)
        if loaded_model is None:
            raise ModelUnavailableError(
                getattr(request.app.state, "model_error", None)
                or "The ambiguity model is not loaded."
            )

        service = AnalyzeService(
            loaded_model,
            rewrite_service=request.app.state.rewrite_service,
            llm_analyzer=getattr(request.app.state, "llm_analyzer", None),
            settings=settings_local,
        )
        try:
            return service.analyze(payload.requirement)
        except ModelUnavailableError:
            raise
        except Exception:
            logger.exception("Unexpected error while analyzing a requirement")
            raise ModelUnavailableError(
                "Inference failed while classifying the requirement."
            ) from None

    @app.post(
        "/api/generate-requirement",
        response_model=GenerateResponse,
        summary="Create a requirement from an idea",
        description=(
            "Turns a natural-language idea into a software requirement, then "
            "runs the same quality analysis used by /api/analyze."
        ),
    )
    def generate_requirement(
        payload: GenerateRequest,
        request: Request,
    ) -> GenerateResponse:
        settings_local: Settings = request.app.state.settings
        loaded_model = getattr(request.app.state, "model", None)
        if loaded_model is None:
            raise ModelUnavailableError(
                getattr(request.app.state, "model_error", None)
                or "The ambiguity model is not loaded."
            )
        analyze_service = AnalyzeService(
            loaded_model,
            rewrite_service=request.app.state.rewrite_service,
            llm_analyzer=getattr(request.app.state, "llm_analyzer", None),
            settings=settings_local,
        )
        service = GenerateService(analyze_service, settings_local)
        try:
            return service.generate(
                payload.idea, payload.requirement_type, payload.details
            )
        except ModelUnavailableError:
            raise
        except Exception:
            logger.exception("Unexpected error while generating a requirement")
            raise ModelUnavailableError(
                "The requirement could not be generated right now."
            ) from None

    return app


def _validation_message(errors: list[dict]) -> str:
    if not errors:
        return "Invalid request."

    first = errors[0]
    loc = first.get("loc") or ()
    msg = str(first.get("msg") or "Invalid request.")
    loc_parts = [str(part) for part in loc if part not in {"body", "__root__"}]

    if "json_invalid" in str(first.get("type", "")) or "JSON decode" in msg:
        return "Request body must be valid JSON."
    if "requirement" in loc_parts and "missing" in str(first.get("type", "")):
        return "Missing required field: requirement."
    if msg.startswith("Value error, "):
        return msg[len("Value error, "):]
    if loc_parts:
        return f"{' -> '.join(loc_parts)}: {msg}"
    return msg


app = create_app()


def run() -> None:
    import os

    import uvicorn

    settings = get_settings()
    port = int(os.environ.get("PORT", settings.port))
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    run()
