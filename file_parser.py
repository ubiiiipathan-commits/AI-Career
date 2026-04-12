"""
file_parser.py — Extract plain text from uploaded resume files.
Supports: PDF, DOCX, TXT
"""

import os
import logging

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def extract_text(filepath: str) -> str:
    """
    Extract and return plain text from a resume file.
    Raises ValueError for unsupported types or empty files.
    """
    ext = filepath.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        return _extract_pdf(filepath)
    elif ext == "docx":
        return _extract_docx(filepath)
    elif ext == "txt":
        return _extract_txt(filepath)
    else:
        raise ValueError(f"Unsupported file type: .{ext}")


def _extract_pdf(filepath: str) -> str:
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        text = "\n".join(text_parts).strip()
        if not text:
            raise ValueError("PDF appears to be empty or scanned (no extractable text).")
        return text
    except ImportError:
        raise ImportError("pdfplumber not installed. Run: pip install pdfplumber")


def _extract_docx(filepath: str) -> str:
    try:
        from docx import Document
        doc  = Document(filepath)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        if not text:
            raise ValueError("DOCX file appears to be empty.")
        return text
    except ImportError:
        raise ImportError("python-docx not installed. Run: pip install python-docx")


def _extract_txt(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read().strip()
    if not text:
        raise ValueError("TXT file is empty.")
    return text