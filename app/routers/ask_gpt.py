from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Literal, Optional

from ..schemas import Source
from ..utils.citations import annotate_answer_with_citations
from ..services.llm import chat_text, chat_messages

router = APIRouter(tags=["assistant"])


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    tenant_id: str
    messages: List[ChatMessage]
    question: Optional[str] = None
    raw_text: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None  # optional override


class AskRequest(BaseModel):
    query: str
    model: Optional[str] = None  # optional override
    temperature: Optional[float] = None
    session_id: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    model: str
    sources: List[Source]

SYSTEM_PROMPT = (
    "Ты юридический ассистент в Казахстане. "
    "Пиши кратко и структурно: нумерованный список рисков и короткие пояснения. "
    "Упоминай точные названия актов и статьи (напр.: 'Гражданский кодекс РК, ст. 610'). "
    "Никаких JSON, префиксов 'Assistant:', эмодзи и лишних маркеров. Только чистый текст."
)

@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    try:
        temp = 0.2 if req.temperature is None else float(req.temperature)
        text, _model = await chat_text(
            SYSTEM_PROMPT,
            req.query,
            temperature=temp,
            force_model=req.model,
            cheap_first=True,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream LLM error: {e}")

    text = text.strip().strip("`").strip()
    text = text.replace("**", "")

    text, sources = annotate_answer_with_citations(text)
    model_used = _model or "unknown"
    payload = AskResponse(
        answer=text,
        model=model_used,
        sources=[Source(**src) for src in sources],
    )
    return JSONResponse(content=payload.model_dump(), headers={"X-LLM-Model": model_used})


@router.post("/chat")
async def chat(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    temp = 0.2 if req.temperature is None else float(req.temperature)

    conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
    conversation.extend([m.model_dump() for m in req.messages])

    if req.question:
        last_user = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
        if (last_user or "").strip() != req.question.strip():
            conversation.append({"role": "user", "content": req.question})

    if req.raw_text:
        context_suffix = "\n\nКонтекст документа (используй при ответе):\n" + req.raw_text
        if conversation and conversation[-1]["role"] == "user":
            conversation[-1]["content"] += context_suffix
        else:
            conversation.append({
                "role": "user",
                "content": context_suffix.strip(),
            })

    try:
        text, model_used = await chat_messages(
            conversation,
            temperature=temp,
            force_model=req.model,
            cheap_first=True,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream LLM error: {e}")

    text = text.strip().strip("`").strip()
    text = text.replace("**", "")
    text, sources = annotate_answer_with_citations(text)
    return {"answer": text, "model": model_used or "unknown", "sources": sources}
