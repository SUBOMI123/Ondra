import json

import httpx

from ondra_core.embeddings import DIMENSIONS, HashEmbedder, VoyageEmbedder, cosine


async def test_voyage_request_shape_and_order():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.url.path, req.headers["authorization"], json.loads(req.content)))
        # Returned out of order on purpose: results must be matched by index.
        return httpx.Response(200, json={"object": "list", "model": "voyage-4", "usage": {"total_tokens": 4},
                                         "data": [{"object": "embedding", "embedding": [0.0, 1.0], "index": 1},
                                                  {"object": "embedding", "embedding": [1.0, 0.0], "index": 0}]})

    e = VoyageEmbedder("pa-test", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await e.embed(["a", "b"], "document") == [[1.0, 0.0], [0.0, 1.0]]
    await e.embed(["q"], "query")
    (path, auth, body), (_, _, qbody) = seen
    assert path == "/v1/embeddings" and auth == "Bearer pa-test"
    assert body == {"input": ["a", "b"], "model": "voyage-4", "input_type": "document", "output_dimension": DIMENSIONS}
    assert qbody["model"] == "voyage-4-lite" and qbody["input_type"] == "query"


async def test_hash_embedder_is_deterministic_and_word_based():
    e = HashEmbedder()
    a, b, c = await e.embed(["opening hours sunday", "are you open on sunday", "lift kits"], "query")
    assert len(a) == DIMENSIONS and await e.embed(["opening hours sunday"], "query") == [a]
    assert cosine(a, b) > cosine(a, c)
