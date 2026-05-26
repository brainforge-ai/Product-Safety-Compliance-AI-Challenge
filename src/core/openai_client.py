"""
Shared OpenAI client and utilities.
"""
from __future__ import annotations
import json
import os
import re
from typing import Optional

from openai import AsyncOpenAI

_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    """Get or create the OpenAI async client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def parse_json_response(content: str) -> dict:
    """Parse JSON from GPT response, handling markdown code blocks."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding JSON object in text
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return {}
