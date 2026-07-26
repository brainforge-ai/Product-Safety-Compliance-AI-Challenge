"""FastAPI application entrypoint.

This module is intentionally thin: it wires together the app factory,
mounts routers, and defines the lifespan hook. No business logic should
live here, per the ports-and-adapters design in docs/ARCHITECTURE.md.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes_evaluate import router as evaluate_router
from app.api.routes_forbidden_list import router as forbidden_list_router
from app.api.routes_health import router as health_router
from app.api.routes_products import router as products_router
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, UnsupportedFileTypeError
from app.core.logging import setup_logging
from app.domain.forbidden_list.repository import ForbiddenListRepository
from app.domain.matching.acronym_matcher import AcronymMatcher
from app.domain.matching.base import Matcher
from app.domain.matching.exact_matcher import ExactMatcher
from app.domain.matching.formula_matcher import FormulaMatcher
from app.domain.matching.fuzzy_matcher import FuzzyMatcher
from app.domain.matching.llm_matcher import LlmMatcher
from app.domain.matching.pipeline import MatchPipeline
from app.infra.db.session import create_db_and_tables, create_db_engine

logger = logging.getLogger(__name__)


def _default_match_pipeline(settings: Settings) -> MatchPipeline:
    matchers: list[Matcher] = [ExactMatcher(), FormulaMatcher(), FuzzyMatcher(), AcronymMatcher()]

    # Tier 5 (optional): registers onto this same pipeline like any other
    # Matcher, since embedding lookup is a synchronous, stateless,
    # per-(ingredient, forbidden_entry) operation -- unlike tier 6, it fits
    # the existing MatchPipeline shape without any changes (see
    # docs/IMPLEMENTATION_PLAN.md Phase 8 notes).
    if settings.enable_embedding_matching:
        from app.domain.matching.embedding_matcher import EmbeddingMatcher
        from app.infra.embeddings.sentence_transformer_encoder import encode, warm_up

        warm_up()
        matchers.append(EmbeddingMatcher(encode))

    # Tiers 1-4 (and 5, if enabled) alone keep the app fully functional with
    # zero API keys (ARCHITECTURE.md Section 6). Tier 6 (LLM) is NOT
    # registered here -- see `_build_llm_matcher` and
    # `domain/matching/llm_matcher.py` for why it's a separate,
    # product-level, async stage instead.
    return MatchPipeline(matchers)


def _build_llm_matcher(settings: Settings) -> LlmMatcher | None:
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


def _load_default_forbidden_list(settings: Settings) -> ForbiddenListRepository:
    path = settings.default_forbidden_list_path
    if not path.is_file():
        logger.warning("Default forbidden list not found at %s; starting with an empty list.", path)
        return ForbiddenListRepository([])
    return ForbiddenListRepository.from_csv(path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings

    # Toggling ENABLE_PERSISTENCE changes only this wiring; no service/route
    # code branches on the flag (ARCHITECTURE.md Section 8).
    if settings.enable_persistence:
        app.state.db_engine = create_db_engine(settings.database_url)
        create_db_and_tables(app.state.db_engine)

    app.state.forbidden_list_repository = _load_default_forbidden_list(settings)
    app.state.match_pipeline = _default_match_pipeline(settings)
    app.state.llm_matcher = _build_llm_matcher(settings)

    yield


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="Product Safety Compliance AI System",
        version="0.1.0",
        lifespan=lifespan,
        # Swagger UI at /docs, ReDoc at /redoc, raw schema at /openapi.json.
        # Set explicitly (matching FastAPI's defaults) so the interactive
        # API docs are a documented, intentional part of the app rather
        # than an implicit default.
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(evaluate_router, prefix="/api", tags=["evaluate"])
    app.include_router(forbidden_list_router, prefix="/api", tags=["forbidden-ingredients"])
    app.include_router(products_router, prefix="/api", tags=["products"])

    # UnsupportedFileTypeError is registered explicitly (ahead of its AppError
    # base) so an unrecognized upload gets 415 rather than the generic 422
    # every other domain exception maps to.
    @app.exception_handler(UnsupportedFileTypeError)
    async def _handle_unsupported_file_type(request, exc: UnsupportedFileTypeError):
        return JSONResponse(status_code=415, content={"detail": str(exc)})

    @app.exception_handler(AppError)
    async def _handle_app_error(request, exc: AppError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app


app = create_app()
