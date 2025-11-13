import json
from typing import Any, Dict, List, Tuple

import httpx

from ..config import settings


PERPLEXITY_BASE_URL = "https://api.perplexity.ai"


class LLMConfigurationError(Exception):
    """Ошибка конфигурации LLM (отсутствует API ключ и т.д.)"""
    pass


class LLMServiceError(Exception):
    """Ошибка при обращении к LLM сервису"""
    pass


async def _pplx_chat(
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    force_model: str | None = None,
    cheap_first: bool | None = None,
) -> Tuple[str, str]:
    if not settings.PERPLEXITY_API_KEY:
        raise LLMConfigurationError(
            "PERPLEXITY_API_KEY is not set. Please configure PERPLEXITY_API_KEY in environment variables."
        )
    
    headers = {
        "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }

    # Build candidate list with cost-aware ordering.
    cheap_first = settings.LLM_PREFER_CHEAPEST if cheap_first is None else cheap_first
    configured = (settings.PERPLEXITY_MODEL or "").strip()
    # Heuristic cost order (cheapest → дороже): small → medium → large → pro.
    cheap_candidates = [
        "sonar-small-chat",
        "llama-3.1-sonar-small-128k-chat",
        "sonar",
        "sonar-medium-chat",
        "llama-3.1-sonar-large-128k-chat",
        "sonar-large-chat",
        "sonar-pro",
    ]
    if cheap_first:
        base = cheap_candidates + ([configured] if configured else [])
    else:
        base = ([configured] if configured else []) + cheap_candidates
    if force_model:
        # Force model goes first
        base = [force_model] + base
    candidates = base
    # Preserve order and uniqueness
    seen = set()
    models_to_try = [m for m in candidates if m and not (m in seen or seen.add(m))]

    async with httpx.AsyncClient(base_url=PERPLEXITY_BASE_URL, timeout=httpx.Timeout(60.0)) as client:
        last_detail = None
        for model in models_to_try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            resp = await client.post("/chat/completions", json=payload, headers=headers)
            if resp.status_code == 400:
                # Check if it's invalid_model and try next candidate
                try:
                    detail_json = resp.json()
                except Exception:
                    detail_json = {"text": resp.text}
                err = detail_json.get("error", {}) if isinstance(detail_json, dict) else {}
                if isinstance(err, dict) and err.get("type") == "invalid_model":
                    last_detail = detail_json
                    continue
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                try:
                    last_detail = resp.json()
                except Exception:
                    last_detail = {"text": resp.text}
                raise LLMServiceError(
                    f"Perplexity API error {resp.status_code}: {last_detail}"
                ) from e
            data = resp.json()
            content = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "") or ""
            model_used = data.get("model") or model
            return content, model_used

    raise LLMServiceError(
        f"Perplexity API invalid_model for all candidates: {models_to_try}. Last detail: {last_detail}"
    )


async def chat_text(
    system: str,
    user: str,
    temperature: float = 0.2,
    *,
    force_model: str | None = None,
    cheap_first: bool | None = None,
) -> Tuple[str, str]:
    """Return (text, model_used). Uses Perplexity when configured, fallback OpenAI otherwise."""
    provider = (settings.LLM_PROVIDER or "perplexity").lower()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    if provider == "perplexity":
        return await _pplx_chat(messages, temperature=temperature, force_model=force_model, cheap_first=cheap_first)

    # Fallback to OpenAI if explicitly requested
    from openai import AsyncOpenAI  # lazy import
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    chat = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        temperature=temperature,
    )
    text = chat.choices[0].message.content or ""
    model_used = settings.OPENAI_MODEL
    return text, model_used


async def chat_messages(
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    *,
    force_model: str | None = None,
    cheap_first: bool | None = None,
) -> Tuple[str, str]:
    """Generic chat helper that preserves the provided conversation turns."""
    if not messages:
        raise ValueError("messages must be a non-empty list")

    provider = (settings.LLM_PROVIDER or "perplexity").lower()

    if provider == "perplexity":
        return await _pplx_chat(
            messages,
            temperature=temperature,
            force_model=force_model,
            cheap_first=cheap_first,
        )

    # Fallback to OpenAI if explicitly requested
    from openai import AsyncOpenAI  # lazy import

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    chat = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        temperature=temperature,
    )
    text = chat.choices[0].message.content or ""
    model_used = settings.OPENAI_MODEL
    return text, model_used


async def chat_json(
    system: str,
    user: str,
    temperature: float = 0.2,
    *,
    force_model: str | None = None,
    cheap_first: bool | None = None,
) -> Tuple[Dict[str, Any], str]:
    """Best-effort JSON response. If model returns non-JSON, wrap it into a JSON object.
    Returns (data, model_used).
    """
    text, model_used = await chat_text(system, user, temperature=temperature, force_model=force_model, cheap_first=cheap_first)
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            data = {"summary": text, "risks": [], "checklist": []}
    except Exception:
        data = {"summary": text, "risks": [], "checklist": []}
    return data, model_used
