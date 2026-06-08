import re
from pathlib import Path


SKILL_KEYWORDS = [
    "python", "sql", "excel", "power bi", "tableau", "machine learning", "pandas",
    "numpy", "react", "fastapi", "flask", "java", "javascript", "aws", "docker",
    "statistics", "nlp", "deep learning", "html", "css", "postgresql"
]


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""
    if suffix == ".docx":
        try:
            from docx import Document

            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _section(text: str, names: list[str]) -> str:
    pattern = "|".join(re.escape(name) for name in names)
    match = re.search(rf"(?is)({pattern})\s*:?\s*(.+?)(\n[A-Z][A-Za-z /&]+:?|\Z)", text)
    return re.sub(r"\s+", " ", match.group(2)).strip()[:600] if match else ""


def analyze_resume(text: str) -> dict[str, object]:
    lower = text.lower()
    skills = sorted({skill.title() for skill in SKILL_KEYWORDS if skill in lower})
    projects = _section(text, ["projects", "academic projects", "personal projects"])
    experience = _section(text, ["experience", "work experience", "internship"])
    education = _section(text, ["education", "academics", "qualification"])
    certifications = _section(text, ["certifications", "certificates", "achievements"])
    question_seeds = []
    for skill in skills[:6]:
        question_seeds.append(f"Walk me through a project where you used {skill}.")
    if projects:
        question_seeds.append("Explain the most technically challenging project from your resume.")
    return {
        "skills": skills,
        "education": education or "Not detected",
        "experience": experience or "Not detected",
        "projects": projects or "Not detected",
        "certifications": certifications or "Not detected",
        "question_seeds": question_seeds[:8],
    }
