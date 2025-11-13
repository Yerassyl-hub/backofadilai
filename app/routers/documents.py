import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import SessionLocal, engine, Base
from ..models import Document, Chunk
from ..schemas import UploadResponse
from ..services.extract import extract_text
from ..services.embedding import embed_texts
from ..utils.text import chunk_text

router = APIRouter(tags=["documents"])

SKIP_DB_INIT = os.getenv("SKIP_DB_INIT", "false").lower() == "true"

@router.on_event("startup")
async def startup():
    if SKIP_DB_INIT:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), tenant_id: str = Form(...)):
    content_bytes = await file.read()
    text = await extract_text(file.filename, content_bytes)
    if not text or len(text.strip()) == 0:
        raise HTTPException(400, "Empty text after extraction")

    chunks = chunk_text(text, target_tokens=300)
    embeddings = await embed_texts(chunks)

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
