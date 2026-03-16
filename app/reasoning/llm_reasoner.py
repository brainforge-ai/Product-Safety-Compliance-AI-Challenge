"""LLM-based reasoner for product safety."""

import os

import requests

from ..logger import logger


def llm_reason(text):
    """
    Ask an LLM to extract harmful/forbidden chemical ingredients from the given text.
    Returns the model's response as a string.
    """
    # Optional module: only enabled if explicitly turned on.
    if os.getenv("ENABLE_LLM_REASONING", "0") != "1":
        raise RuntimeError(
            "LLM reasoning is disabled. Set ENABLE_LLM_REASONING=1 to enable local Llama 3 reasoning."
        )

    prompt = f"""
    Extract any harmful or forbidden chemical ingredients from:

    {text}
    """

    # Default to Ollama local server + Llama 3.
    # Requirements:
    # - Install Ollama
    # - Run: ollama pull llama3
    # - Ensure the Ollama server is running (default: http://localhost:11434)
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = os.getenv("LLM_MODEL", "llama3")

    # Use a shorter timeout so we fail fast when Ollama is slow or unavailable
    try:
        timeout_sec = int(os.getenv("OLLAMA_TIMEOUT", "25"))
    except ValueError as exc:
        raise RuntimeError("OLLAMA_TIMEOUT must be an integer number of seconds") from exc

    try:
        response = requests.post(
            f"{ollama_host}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=timeout_sec,
        )
    except requests.RequestException as exc:
        logger.warning("Ollama request failed: %s", exc)
        raise RuntimeError("LLM reasoning request failed") from exc

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        logger.warning(
            "Ollama returned HTTP %s for model=%s host=%s: %s",
            response.status_code,
            model,
            ollama_host,
            response.text[:500],
        )
        raise RuntimeError(f"LLM reasoning request failed with status {response.status_code}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("Ollama returned non-JSON response for model=%s", model)
        raise RuntimeError("LLM reasoning returned an invalid JSON response") from exc

    message = data.get("message")
    if not isinstance(message, dict):
        logger.warning("Ollama response missing message object: %s", data)
        raise RuntimeError("LLM reasoning response missing message payload")

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        logger.warning("Ollama response missing message content: %s", data)
        raise RuntimeError("LLM reasoning response missing content")

    return content
