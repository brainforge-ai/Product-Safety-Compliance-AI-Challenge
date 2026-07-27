"""FastAPI dependency providers."""

from collections.abc import Iterator

from fastapi import Request

from app.core.config import Settings
from app.domain.forbidden_list.repository import ForbiddenListRepository
from app.domain.matching.llm_matcher import LlmMatcher
from app.domain.matching.pipeline import MatchPipeline
from app.domain.parsing.llm_fallback import LlmFallbackExtractor
from app.domain.persistence.base import EvaluationRepository
from app.domain.persistence.noop_evaluation_repository import NoopEvaluationRepository
from app.infra.db.evaluation_repository import SqliteEvaluationRepository
from app.infra.db.session import get_session


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_evaluation_repository(request: Request) -> Iterator[EvaluationRepository]:
    settings = request.app.state.settings
    if not settings.enable_persistence:
        yield NoopEvaluationRepository()
        return

    engine = request.app.state.db_engine
    with get_session(engine) as session:
        yield SqliteEvaluationRepository(session)


def get_forbidden_list_repository(request: Request) -> ForbiddenListRepository:
    return request.app.state.forbidden_list_repository


def get_match_pipeline(request: Request) -> MatchPipeline:
    return request.app.state.match_pipeline


def get_llm_matcher(request: Request) -> LlmMatcher | None:
    return request.app.state.llm_matcher


def get_llm_extraction_fallback(request: Request) -> LlmFallbackExtractor | None:
    return request.app.state.llm_extraction_fallback
