
import io
from pdfminer.high_level import extract_text as pdf_extract
from docx import Document as DocxDocument
import chardet

async def extract_text(filename: str, content: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return pdf_extract(io.BytesIO(content))
    if name.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    enc = chardet.detect(content).get("encoding") or "utf-8"
    try:
        return content.decode(enc, errors="ignore")
    except Exception:
        return content.decode("utf-8", errors="ignore")
