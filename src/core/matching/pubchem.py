"""
PubChem API client for chemical identifier resolution.

Features:
- CID lookup by name or formula
- Synonym retrieval for bidirectional matching
- In-memory caching to avoid repeated API calls
- Concurrency limiting via semaphore (default: 3 concurrent requests)
- Graceful fallback on errors
- Shared HTTP client for connection reuse
"""
from __future__ import annotations
import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


class PubChemClient:
    """Async PubChem API client with caching and rate limiting."""

    def __init__(self, max_concurrent: int = 3):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._cid_cache: dict[str, list[int]] = {}
        self._synonym_cache: dict[str, list[str]] = {}
        self._stats = {"api_calls": 0, "cache_hits": 0}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @property
    def stats(self) -> dict:
        return self._stats.copy()

    async def _fetch_json(self, url: str) -> Optional[dict]:
        """Fetch JSON from URL with rate limiting and error handling."""
        async with self._semaphore:
            try:
                client = await self._get_client()
                self._stats["api_calls"] += 1
                resp = await client.get(url)
                if resp.status_code == 404:
                    return None  # Not found is not an error
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503:
                    # Rate limited - wait and retry once
                    logger.warning("PubChem rate limited, waiting 1s...")
                    await asyncio.sleep(1.0)
                    try:
                        client = await self._get_client()
                        resp = await client.get(url)
                        resp.raise_for_status()
                        return resp.json()
                    except Exception:
                        logger.error(f"PubChem retry failed for {url}")
                        return None
                logger.error(f"PubChem HTTP error: {e}")
                return None
            except Exception as e:
                logger.error(f"PubChem request failed: {e}")
                return None

    async def get_cids_by_name(self, name: str) -> list[int]:
        """Get PubChem CIDs for a chemical name."""
        cache_key = f"name:{name.lower()}"
        if cache_key in self._cid_cache:
            self._stats["cache_hits"] += 1
            return self._cid_cache[cache_key]

        encoded_name = name.replace(" ", "%20").replace(",", "%2C")
        url = f"{PUBCHEM_BASE}/compound/name/{encoded_name}/cids/JSON"

        data = await self._fetch_json(url)
        cids = []
        if data and "IdentifierList" in data:
            cids = data["IdentifierList"].get("CID", [])

        self._cid_cache[cache_key] = cids
        return cids

    async def get_cids_by_formula(self, formula: str) -> list[int]:
        """Get PubChem CIDs for a molecular formula."""
        cache_key = f"formula:{formula}"
        if cache_key in self._cid_cache:
            self._stats["cache_hits"] += 1
            return self._cid_cache[cache_key]

        url = f"{PUBCHEM_BASE}/compound/fastformula/{formula}/cids/JSON"

        data = await self._fetch_json(url)
        cids = []
        if data and "IdentifierList" in data:
            cids = data["IdentifierList"].get("CID", [])

        self._cid_cache[cache_key] = cids
        return cids

    async def get_synonyms_by_cid(self, cid: int) -> list[str]:
        """
        Get synonyms for a compound by CID.

        This avoids redundant CID lookups when CIDs are already known.
        """
        cache_key = f"synonyms_cid:{cid}"
        if cache_key in self._synonym_cache:
            self._stats["cache_hits"] += 1
            return self._synonym_cache[cache_key]

        url = f"{PUBCHEM_BASE}/compound/cid/{cid}/synonyms/JSON"

        data = await self._fetch_json(url)
        synonyms = []
        if data and "InformationList" in data:
            info = data["InformationList"].get("Information", [])
            if info:
                synonyms = info[0].get("Synonym", [])[:20]  # Limit to top 20

        self._synonym_cache[cache_key] = synonyms
        return synonyms

    async def get_synonyms(self, identifier: str, is_formula: bool = False) -> list[str]:
        """
        Get synonyms for a compound.

        This is key for bidirectional matching - e.g., get all names for "C6H6"
        to enable matching "Benzene" against the formula in forbidden list.
        """
        cache_key = f"synonyms:{identifier}"
        if cache_key in self._synonym_cache:
            self._stats["cache_hits"] += 1
            return self._synonym_cache[cache_key]

        # First get CID, then get synonyms
        if is_formula:
            cids = await self.get_cids_by_formula(identifier)
        else:
            cids = await self.get_cids_by_name(identifier)

        if not cids:
            self._synonym_cache[cache_key] = []
            return []

        # Get synonyms for first CID (most relevant)
        synonyms = await self.get_synonyms_by_cid(cids[0])
        self._synonym_cache[cache_key] = synonyms
        return synonyms

    async def get_cid_with_synonyms(
        self, identifier: str, is_formula: bool = False
    ) -> tuple[list[int], list[str]]:
        """
        Get both CIDs and synonyms efficiently.

        Fetches CIDs first, then uses the CID directly to get synonyms,
        avoiding redundant lookups.
        """
        if is_formula:
            cids = await self.get_cids_by_formula(identifier)
        else:
            cids = await self.get_cids_by_name(identifier)

        if not cids:
            return [], []

        # Use CID directly to get synonyms (avoids re-fetching CIDs)
        synonyms = await self.get_synonyms_by_cid(cids[0])
        return cids, synonyms
