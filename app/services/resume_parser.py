"""Resume upload parsing: PDF, DOCX and plain text extraction plus
section-oriented NER-style parsing into a structured profile."""
import io
import re
from app.services.matching_service import matching_service

SECTION_HEADERS = {
    "education": ["education", "academic"],
    "experience": ["experience", "employment", "work history"],
    "skills": ["skills", "technologies", "technical skills"],
    "projects": ["projects"],
    "certifications": ["certifications", "certificates"],
}


def extract_text(filename: str, content: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception:
            return ""
    if name.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return ""
    try:
        return content.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def parse_resume(text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    sections: dict = {k: [] for k in SECTION_HEADERS}
    current = None
    for line in lines:
        low = line.lower()
        matched_section = None
        for section, keys in SECTION_HEADERS.items():
            if any(low.startswith(k) or low == k for k in keys) and len(line) < 40:
                matched_section = section
                break
        if matched_section:
            current = matched_section
            continue
        if current:
            sections[current].append(line)
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    phone = re.search(r"(\+?\d[\d\s-]{8,}\d)", text)
    skills = sorted(matching_service._extract_skills(text))
    return {
        "email": email.group(0) if email else None,
        "phone": phone.group(0).strip() if phone else None,
        "detected_skills": skills,
        "sections": {k: v for k, v in sections.items() if v},
        "word_count": len(text.split()),
    }
