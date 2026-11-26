"""Text embeddings for knowledge search.

`VoyageEmbedder` calls Voyage AI (checked against docs.voyageai.com on 2026-11-26): POST /v1/embeddings with
`Authorization: Bearer`, body {input, model, input_type: "query" | "document", output_dimension}, response
data[].embedding in input order. Dealer answers are embedded with voyage-4, customer questions with the faster
voyage-4-lite; Voyage documents that all voyage-4 series embeddings are compatible with each other.

`HashEmbedder` is the local mock: deterministic, no network, crude word overlap. It keeps the system and tests
running with no account. Vectors from different embedders never mix: every stored vector records its `space`.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Literal, Protocol

import httpx

DIMENSIONS = 1024
InputType = Literal["query", "document"]


class Embedder(Protocol):
    space: str  # vectors are only comparable within the same space

    async def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]: ...


class VoyageEmbedder:
    space = "voyage-4"

    def __init__(self, api_key: str, *, document_model: str = "voyage-4", query_model: str = "voyage-4-lite",
                 base_url: str = "https://api.voyageai.com", client: httpx.AsyncClient | None = None) -> None:
        self.api_key = api_key
        self.models = {"document": document_model, "query": query_model}
        self.base_url = base_url.rstrip("/")
        self._client = client

    async def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        if not texts:
            return []
        client = self._client or httpx.AsyncClient(timeout=15)
        try:
            r = await client.post(
                f"{self.base_url}/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"input": texts, "model": self.models[input_type], "input_type": input_type,
                      "output_dimension": DIMENSIONS},
            )
            r.raise_for_status()
        finally:
            if self._client is None:
                await client.aclose()
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]


class HashEmbedder:
    """Bag of words hashed into a fixed-size vector. Not semantic; for local runs and tests only."""

    space = "hash-v1"

    async def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * DIMENSIONS
            for w in re.findall(r"[a-z0-9áéíóúñ]+", t.lower()):
                if len(w) < 3:
                    continue
                w = w.rstrip("s")
                v[int(hashlib.blake2b(w.encode(), digest_size=4).hexdigest(), 16) % DIMENSIONS] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


def cosine(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb) if na and nb else 0.0


def make_embedder(voyage_api_key: str | None) -> Embedder:
    return VoyageEmbedder(voyage_api_key) if voyage_api_key else HashEmbedder()


# Below this cosine similarity a knowledge answer counts as "not relevant", so the AI hands off instead of guessing.
# Measured on the seed answers with voyage-4/voyage-4-lite: relevant matches scored 0.42 to 0.53, unrelated
# questions 0.10 to 0.33. Re-measure when the knowledge base or the models change.
MIN_SIMILARITY = {"voyage-4": 0.38, "hash-v1": 0.25}
