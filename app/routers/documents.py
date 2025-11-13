import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_session_local, get_engine, Base, SKIP_DB
from ..models import Document, Chunk
from ..schemas import UploadResponse
from ..services.extract import extract_text
from ..services.embedding import embed_texts
from ..utils.text import chunk_text

router = APIRouter(tags=["documents"])

# Инициализация БД на startup убрана - приложение запускается без подключения к БД

@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), tenant_id: str = Form(...)):
    content_bytes = await file.read()
    text = await extract_text(file.filename, content_bytes)
    if not text or len(text.strip()) == 0:
        raise HTTPException(400, "Empty text after extraction")

    chunks = chunk_text(text, target_tokens=300)
    embeddings = await embed_texts(chunks)

    if SKIP_DB:
        raise HTTPException(503, "Database is disabled. Set SKIP_DB=false to enable.")

    SessionLocal = get_session_local()
    if SessionLocal is None:
        raise HTTPException(503, "Database connection is not available.")

    async with SessionLocal() as session:  # type: AsyncSession
        doc = Document(tenant_id=tenant_id, filename=file.filename, content=text[:10000])
        session.add(doc)
        await session.flush()

        # Сохраняем эмбеддинг как список чисел, без обёртки {"v": ...}
        for i, (t, e) in enumerate(zip(chunks, embeddings), start=1):
            c = Chunk(document_id=doc.id, tenant_id=tenant_id, ordinal=i, text=t, embedding=e)
            session.add(c)

        await session.commit()
        return UploadResponse(document_id=doc.id, chunks=len(chunks))
