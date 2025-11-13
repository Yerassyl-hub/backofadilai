from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import documents, analyze, ask_gpt

app = FastAPI(title="Adil AI MVP", version="0.1.1")
app.add_middleware(CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health(): return {"status": "ok"}

# Без Depends(auth_dep)
app.include_router(documents.router, prefix="/v1")
app.include_router(analyze.router,  prefix="/v1")
app.include_router(ask_gpt.router,  prefix="/v1")
