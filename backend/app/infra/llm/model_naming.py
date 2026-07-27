"""Shared model-name handling for Pydantic AI adapters."""

_GOOGLE_PREFIX = "google:"


def strip_provider_prefix(model_name: str) -> str:
    if model_name.startswith(_GOOGLE_PREFIX):
        return model_name[len(_GOOGLE_PREFIX) :]
    return model_name
