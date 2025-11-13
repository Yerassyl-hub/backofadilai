import re
import urllib.parse
from typing import Any, Dict, List, Tuple

# Находим упоминания вида "Гражданский кодекс РК, ст. 610" и т.п.
PATTERNS = [
    r"(Гражданский кодекс РК[^,]*,\s*ст\.?\s*\d+)",
    r"(Трудовой кодекс РК[^,]*,\s*ст\.?\s*\d+)",
    r"(Налоговый кодекс РК[^,]*,\s*ст\.?\s*\d+)",
    r"(КоАП РК[^,]*,\s*ст\.?\s*\d+)",
]


def _collect_citations(text: str) -> List[str]:
    """Return citations in order of appearance without duplicates."""
    results: List[Tuple[int, str]] = []
    seen: set[str] = set()
    for pattern in PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            value = match.group(0).strip()
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            results.append((match.start(), value))
    results.sort(key=lambda item: item[0])
    return [value for _, value in results]


def adilet_link(query: str) -> str:
    q = urllib.parse.quote(query)
    return f"https://adilet.zan.kz/rus/search?q={q}"


def _insert_marker(text: str, needle: str, idx: int) -> str:
    pattern = re.compile(re.escape(needle) + r"(?!\s*\[\d+\])", flags=re.IGNORECASE)

    def _repl(match: re.Match[str]) -> str:
        return f"{match.group(0)} [{idx}]"

    new_text, count = pattern.subn(_repl, text, count=1)
    if count:
        return new_text

    marker = f"[{idx}]"
    if marker in text:
        return text
    suffix = " " if text and not text.endswith((" ", "\n")) else ""
    return f"{text}{suffix}{marker}" if text else marker


def annotate_answer_with_citations(answer: str) -> Tuple[str, List[Dict[str, Any]]]:
    citations = _collect_citations(answer)
    if not citations:
        return answer, []

    annotated = answer
    sources: List[Dict[str, Any]] = []
    for idx, cite in enumerate(citations, start=1):
        sources.append({
            "id": idx,
            "title": cite,
            "url": adilet_link(cite),
            "snippet": None,
            "referenceIndex": idx,
        })
        annotated = _insert_marker(annotated, cite, idx)
    return annotated, sources


def ensure_markers_for_sources(text: str, sources: List[Dict[str, Any]]) -> str:
    annotated = text or ""
    for src in sorted(sources, key=lambda item: item.get("id", 0) or 0):
        sid = src.get("id")
        if not isinstance(sid, int) or sid <= 0:
            continue
        marker = f"[{sid}]"
        if marker in annotated:
            continue
        prefix = " " if annotated and not annotated.endswith((" ", "\n")) else ""
        annotated = f"{annotated}{prefix}{marker}" if annotated else marker
    return annotated


def normalize_sources(raw_sources: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in raw_sources:
        if isinstance(item, dict):
            url = item.get("url") or item.get("link")
            if not isinstance(url, str) or not url.strip():
                continue
            sid = item.get("id") or item.get("index") or item.get("ordinal") or item.get("order")
            try:
                sid_int = int(sid) if sid is not None else None
            except (TypeError, ValueError):
                sid_int = None
            normalized.append({
                "id": sid_int,
                "title": item.get("title") or item.get("name"),
                "url": url.strip(),
                "snippet": item.get("snippet") or item.get("description") or item.get("preview"),
                "referenceIndex": item.get("referenceIndex") or item.get("id") or item.get("index") or item.get("ordinal"),
            })
        elif isinstance(item, str) and item.strip():
            normalized.append({
                "id": None,
                "title": None,
                "url": item.strip(),
                "snippet": None,
                "referenceIndex": None,
            })

    used: set[int] = set()
    next_id = 1
    for entry in normalized:
        sid = entry["id"]
        if isinstance(sid, int) and sid > 0 and sid not in used:
            used.add(sid)
            next_id = max(next_id, sid + 1)
            entry["referenceIndex"] = entry.get("referenceIndex") or sid
            continue
        while next_id in used:
            next_id += 1
        entry["id"] = next_id
        entry["referenceIndex"] = entry.get("referenceIndex") or next_id
        used.add(next_id)
        next_id += 1

    normalized.sort(key=lambda item: item["id"])
    return normalized


def append_sources_block(answer: str) -> str:
    """Legacy helper to append bullet list of sources beneath the answer."""
    citations = _collect_citations(answer)
    if not citations:
        return answer
    lines = ["", "Источники:"]
    for idx, cite in enumerate(citations, start=1):
        lines.append(f"- {cite} — {adilet_link(cite)}")
    return answer.rstrip() + "\n" + "\n".join(lines) + "\n"
