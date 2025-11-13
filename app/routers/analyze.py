
from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import SessionLocal
from ..schemas import AnalyzeRequest, AnalyzeResponse, Citation
from ..services.rag import build_prompt_and_citations, call_llm
from ..services.risk_rules import rule_flags

router = APIRouter(tags=["analyze"])

@router.post("/analyze/contract", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    if not req.document_id and not req.text:
        raise HTTPException(400, "Provide document_id or raw text")
    async with SessionLocal() as session:  # type: AsyncSession
        prompt, cits = await build_prompt_and_citations(session, req)
        try:
            llm_out = await call_llm(prompt)
        except Exception as e:
            # Return upstream error to client without crashing the server
            raise HTTPException(status_code=502, detail=f"Upstream LLM error: {e}")
        risks_extra = rule_flags(llm_out.get("summary","") + " " + req.query)
        return AnalyzeResponse(
            summary=llm_out.get("summary",""),
            risks=(llm_out.get("risks",[]) + risks_extra),
            checklist=llm_out.get("checklist",[]),
            citations=[Citation(**c) for c in cits],
            model=llm_out.get("model","unknown")
        )
