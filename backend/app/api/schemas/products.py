from pydantic import BaseModel

from app.domain.models import StoredEvaluation


class EvaluationHistoryResponse(BaseModel):
    items: list[StoredEvaluation]
    limit: int
    offset: int
