"""Forbidden-list CSV upload and replacement."""

from fastapi import UploadFile

from app.core.exceptions import ParsingError
from app.domain.forbidden_list.repository import ForbiddenListRepository
from app.domain.persistence.base import EvaluationRepository


async def replace_forbidden_list_from_upload(
    upload: UploadFile,
    repository: ForbiddenListRepository,
    evaluation_repository: EvaluationRepository,
) -> list[str]:
    """Decode a CSV upload, replace the in-memory list, and persist a version snapshot."""
    raw_bytes = await upload.read()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParsingError("Forbidden list CSV must be UTF-8 encoded") from exc

    entries = ForbiddenListRepository.from_csv_text(text).get_all()
    if not entries:
        raise ParsingError("Forbidden list CSV contained no ingredient entries")

    repository.replace(entries)
    evaluation_repository.save_forbidden_list_version(entries)
    return entries
