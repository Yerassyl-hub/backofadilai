
from pydantic import BaseModel, Field
from typing import Any, List, Optional
from uuid import UUID

class UploadResponse(BaseModel):
    document_id: UUID
    chunks: int

class AnalyzeRequest(BaseModel):
    tenant_id: str
    document_id: Optional[UUID] = None
    text: Optional[str] = None
    query: str = "Сделай резюме документа и найди риски."

class Citation(BaseModel):
    document_id: UUID
    chunk_id: UUID
    ordinal: int
    preview: str

class Source(BaseModel):
    id: int
    title: Optional[str] = None
    url: str
    snippet: Optional[str] = None
    referenceIndex: Optional[int] = None

    def model_post_init(self, __context: Any) -> None:
        if self.referenceIndex is None:
            self.referenceIndex = self.id

class AnalyzeResponse(BaseModel):
    summary: str
    risks: List[str]
    checklist: List[str]
    citations: List[Citation]
    model: str
    sources: List[Source] = Field(default_factory=list)
    disclaimer: str = Field(default="Информационный сервис. Не юридическая консультация.")
