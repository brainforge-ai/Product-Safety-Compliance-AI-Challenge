from pydantic import BaseModel


class ForbiddenListResponse(BaseModel):
    ingredients: list[str]
