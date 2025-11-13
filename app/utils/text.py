
import re

def chunk_text(text: str, target_tokens: int = 300):
    paras = re.split(r'\n\s*\n', text)
    chunks = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) < target_tokens * 4:
            buf += (("\n" if buf else "") + p)
        else:
            if buf:
                chunks.append(buf.strip())
            buf = p
    if buf:
        chunks.append(buf.strip())
    return [c for c in chunks if c]
