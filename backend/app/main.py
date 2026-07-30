"""FastAPI app factory and lifespan wiring."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes_evaluate import router as evaluate_router
from app.api.routes_forbidden_list import router as forbidden_list_router
from app.api.routes_health import router as health_router
from app.api.routes_products import router as products_router
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, UnsupportedFileTypeError, UploadTooLargeError
from app.core.logging import setup_logging
from app.domain.forbidden_list.repository import ForbiddenListRepository
from app.domain.matching.acronym_matcher import AcronymMatcher
from app.domain.matching.base import Matcher
from app.domain.matching.exact_matcher import ExactMatcher
from app.domain.matching.formula_matcher import FormulaMatcher
from app.domain.matching.fuzzy_matcher import FuzzyMatcher
from app.domain.matching.llm_matcher import LlmMatcher
from app.domain.matching.pipeline import MatchPipeline
from app.domain.parsing.llm_fallback import LlmFallbackExtractor
from app.infra.db.session import create_db_and_tables, create_db_engine

logger = logging.getLogger(__name__)


def _default_match_pipeline(settings: Settings) -> MatchPipeline:
    """Build the tiered matcher pipeline, optionally including embeddings."""
    matchers: list[Matcher] = [ExactMatcher(), FormulaMatcher(), FuzzyMatcher(), AcronymMatcher()]

    if settings.enable_embedding_matching:
        from app.domain.matching.embedding_matcher import EmbeddingMatcher
        from app.infra.embeddings.sentence_transformer_encoder import (
            SentenceTransformerEncoder,
            warm_up,
        )

        warm_up()
        matchers.append(EmbeddingMatcher(SentenceTransformerEncoder()))

    return MatchPipeline(matchers)


def _build_llm_matcher(settings: Settings) -> LlmMatcher | None:
    """Create the tier-6 LLM matcher when matching is enabled and configured."""
    if not settings.enable_llm_matching:
        return None
    if not settings.google_api_key:
        logger.warning(
            "ENABLE_LLM_MATCHING is set but GOOGLE_API_KEY is missing; "
            "tier 6 (LLM matching) will not be registered."
        )
        return None

    from app.infra.cache.llm_response_cache import LlmResponseCache
    from app.infra.llm.pydantic_ai_client import PydanticAiLlmClient

    return LlmMatcher(
        PydanticAiLlmClient(settings),
        LlmResponseCache(),
        timeout_seconds=settings.llm_timeout_seconds,
    )


def _build_llm_extraction_fallback(settings: Settings) -> LlmFallbackExtractor | None:
    """Create the LLM extraction fallback when LLM features are enabled."""
    if not settings.enable_llm_matching:
        return None
    if not settings.google_api_key:
        return None

    from app.infra.llm.pydantic_ai_extraction_fallback import PydanticAiExtractionFallback

    return LlmFallbackExtractor(
        PydanticAiExtractionFallback(settings),
        timeout_seconds=settings.llm_timeout_seconds,
    )


def _load_default_forbidden_list(settings: Settings) -> ForbiddenListRepository:
    """Load the startup forbidden list from disk, or start empty if missing."""
    path = settings.default_forbidden_list_path
    if not path.is_file():
        logger.warning("Default forbidden list not found at %s; starting with an empty list.", path)
        return ForbiddenListRepository([])
    return ForbiddenListRepository.from_csv(path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize settings, optional DB, forbidden list, and matchers at startup."""
    settings = get_settings()
    app.state.settings = settings

    if settings.enable_persistence:
        app.state.db_engine = create_db_engine(settings.database_url)
        create_db_and_tables(app.state.db_engine)

    app.state.forbidden_list_repository = _load_default_forbidden_list(settings)
    app.state.match_pipeline = _default_match_pipeline(settings)
    app.state.llm_matcher = _build_llm_matcher(settings)
    app.state.llm_extraction_fallback = _build_llm_extraction_fallback(settings)

    yield


def create_app() -> FastAPI:
    """Construct the FastAPI application with routes and exception handlers."""
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="Product Safety Compliance AI System",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(evaluate_router, prefix="/api", tags=["evaluate"])
    app.include_router(forbidden_list_router, prefix="/api", tags=["forbidden-ingredients"])
    app.include_router(products_router, prefix="/api", tags=["products"])

    @app.exception_handler(UploadTooLargeError)
    async def _handle_upload_too_large(request, exc: UploadTooLargeError):
        return JSONResponse(status_code=413, content={"detail": str(exc)})

    # UnsupportedFileTypeError must register before AppError (415 vs 422).
    @app.exception_handler(UnsupportedFileTypeError)
    async def _handle_unsupported_file_type(request, exc: UnsupportedFileTypeError):
        return JSONResponse(status_code=415, content={"detail": str(exc)})

    @app.exception_handler(AppError)
    async def _handle_app_error(request, exc: AppError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app


app = create_app()
