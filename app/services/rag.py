from typing import List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import numpy as np
from ..models import Chunk
from ..config import settings
from ..schemas import AnalyzeRequest
from .llm import chat_json

SYSTEM = (
    "Ты юридический ассистент для МСБ в Казахстане. "
    "Отвечай кратко и понятно. Пиши на русском. "
    "Ты даешь информационные пояснения, не юридические советы. "
    "Всегда добавляй чек-лист действий. Используй цитаты из контекста, если есть."
)

USER_TEMPLATE = """Текст запроса: {query}

Контекстные фрагменты:
{contexts}

Задача: Сделай краткое резюме, перечисли риски и сформируй чек-лист действий.
Ответ в JSON с полями: summary, risks[], checklist[].
"""

def _to_vec(raw) -> np.ndarray:
    # Совместимость со старым форматом {"v":[...]}
    if isinstance(raw, dict):
        raw = raw.get("v", [])
    if raw is None:
        raw = []
    # Приведение к float32
    return np.asarray([float(x) for x in raw], dtype=np.float32).reshape(-1)

async def _top_chunks(session: AsyncSession, document_id: UUID, query: str, k: int = 6):
    # Embeddings: keep using OpenAI embeddings as configured
    from openai import AsyncOpenAI  # local import to avoid hard dependency when provider is Perplexity
    _emb_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    q_emb = (await _emb_client.embeddings.create(model=settings.OPENAI_EMBED_MODEL, input=[query])).data[0].embedding
    q = _to_vec(q_emb)

    res = await session.execute(
        select(Chunk).where(Chunk.document_id == document_id)
    )
    rows: List[Chunk] = [r[0] for r in res.fetchall()]

    scored: List[Tuple[float, Chunk]] = []
    for ch in rows:
        e = _to_vec(ch.embedding)
        score = 0.0 if e.size == 0 else float(np.dot(q, e) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-8))
        scored.append((score, ch))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]

async def build_prompt_and_citations(session: AsyncSession, req: AnalyzeRequest) -> Tuple[str, List[Dict[str, Any]]]:
    contexts: List[str] = []
    citations: List[Dict[str, Any]] = []
    if req.document_id:
        rows = await _top_chunks(session, req.document_id, req.query, 6)
        for r in rows:
            contexts.append(f"[{r.ordinal}] {r.text[:800]}")
            citations.append({
                "document_id": r.document_id, "chunk_id": r.id, "ordinal": r.ordinal,
                "preview": r.text[:200]
            })
    else:
        contexts = [req.text[:2000] if req.text else "нет контекста"]

    ctx = "\n\n".join(contexts) if contexts else "нет контекста"
    prompt = USER_TEMPLATE.format(query=req.query, contexts=ctx)
    return prompt, citations

async def call_llm(prompt: str) -> Dict[str, Any]:
    data, model_used = await chat_json(SYSTEM, prompt, temperature=0.2)
    data["model"] = model_used
    return data
