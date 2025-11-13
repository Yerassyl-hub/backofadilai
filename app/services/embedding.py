from typing import List
from openai import AsyncOpenAI
from ..config import settings

_client: AsyncOpenAI | None = None
def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client

async def embed_texts(chunks: List[str]) -> List[List[float]]:
    client = get_client()
    resp = await client.embeddings.create(model=settings.OPENAI_EMBED_MODEL, input=chunks)
    return [d.embedding for d in resp.data]
