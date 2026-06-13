import asyncio
import inspect
from threading import Lock
from typing import Any, Awaitable, Callable

import httpx

from app.config import get_settings


MODEL_NAME = "all-MiniLM-L6-v2"
SUPABASE_MODEL_NAME = "gte-small"
EMBEDDING_DIMENSIONS = 384
_model: Any = None
_model_lock = Lock()


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                try:
                    _model = SentenceTransformer(
                        MODEL_NAME,
                        local_files_only=True,
                    )
                except OSError:
                    _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_local(text: str) -> list[float]:
    vector = get_model().encode(text, normalize_embeddings=True)
    values = vector.tolist()
    return validate_embedding(values)


def validate_embedding(values: list[float]) -> list[float]:
    if len(values) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Embedding model returned {len(values)} dimensions; "
            f"expected {EMBEDDING_DIMENSIONS}"
        )
    return [float(value) for value in values]


async def embed_remote(text: str) -> list[float]:
    settings = get_settings()
    if not settings.embedding_api_url or not settings.embedding_api_secret:
        raise RuntimeError(
            "Supabase embedding URL and secret must be configured"
        )
    async with httpx.AsyncClient(
        timeout=settings.embedding_request_timeout_seconds
    ) as client:
        response = await client.post(
            settings.embedding_api_url,
            json={"input": text},
            headers={"X-Embedding-Secret": settings.embedding_api_secret},
        )
        response.raise_for_status()
        payload = response.json()
    values = payload.get("embedding")
    if not isinstance(values, list):
        raise ValueError("Embedding service returned an invalid response")
    return validate_embedding(values)


async def embed(text: str) -> list[float]:
    settings = get_settings()
    if settings.embedding_provider == "supabase":
        return await embed_remote(text)
    return await asyncio.to_thread(embed_local, text)


async def call_embedder(
    text: str,
    embed_fn: Callable[
        [str],
        list[float] | Awaitable[list[float]],
    ]
    | None = None,
) -> list[float]:
    result = embed(text) if embed_fn is None else embed_fn(text)
    if inspect.isawaitable(result):
        result = await result
    return validate_embedding(result)
