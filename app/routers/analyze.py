
from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_session_local, SKIP_DB
from ..schemas import AnalyzeRequest, AnalyzeResponse, Citation
from ..services.rag import build_prompt_and_citations, call_llm
from ..services.risk_rules import rule_flags
from ..services.llm import LLMConfigurationError, LLMServiceError

router = APIRouter(tags=["analyze"])

@router.post("/analyze/contract", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    if not req.document_id and not req.text:
        raise HTTPException(400, "Provide document_id or raw text")
    
    # Если БД отключена, но есть raw text - работаем без БД
    if SKIP_DB and req.document_id:
        raise HTTPException(503, "Database is disabled. Use 'text' parameter instead of 'document_id'.")
    
    if SKIP_DB or req.text:
        # Работаем без БД, используя только raw text
        from ..services.rag import call_llm
        prompt = f"Текст запроса: {req.query}\n\nКонтекстные фрагменты:\n{req.text[:2000] if req.text else 'нет контекста'}\n\nЗадача: Сделай краткое резюме, перечисли риски и сформируй чек-лист действий."
        try:
            llm_out = await call_llm(prompt)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Upstream LLM error: {e}")
        risks_extra = rule_flags(llm_out.get("summary","") + " " + req.query)
        return AnalyzeResponse(
            summary=llm_out.get("summary",""),
            risks=(llm_out.get("risks",[]) + risks_extra),
            checklist=llm_out.get("checklist",[]),
            citations=[],
            model=llm_out.get("model","unknown")
        )
    
    SessionLocal = get_session_local()
    if SessionLocal is None:
        raise HTTPException(503, "Database connection is not available.")
    
    async with SessionLocal() as session:  # type: AsyncSession
        prompt, cits = await build_prompt_and_citations(session, req)
        try:
            llm_out = await call_llm(prompt)
        except LLMConfigurationError as e:
            raise HTTPException(
                status_code=502,
                detail="Сервис временно недоступен из-за проблем с конфигурацией на сервере. Пожалуйста, обратитесь к администратору."
            )
        except LLMServiceError as e:
            raise HTTPException(
                status_code=502,
                detail="Сервер временно недоступен. Пожалуйста, попробуйте позже."
            )
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
