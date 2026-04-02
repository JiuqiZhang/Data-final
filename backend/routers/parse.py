import io
from fastapi import APIRouter, UploadFile, File, HTTPException
from pypdf import PdfReader
from docx import Document

router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}


def _extract_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _extract_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()


@router.post("/parse-resume")
async def parse_resume(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES and not (
        file.filename or ""
    ).lower().endswith((".pdf", ".docx", ".doc")):
        raise HTTPException(
            status_code=422,
            detail="Only PDF and DOCX files are supported.",
        )

    data = await file.read()
    name = (file.filename or "").lower()

    try:
        if name.endswith(".pdf") or file.content_type == "application/pdf":
            text = _extract_pdf(data)
        else:
            text = _extract_docx(data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {str(e)}")

    if not text:
        raise HTTPException(status_code=422, detail="No text could be extracted from the file.")

    return {"text": text}
