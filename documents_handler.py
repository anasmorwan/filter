import os
from docx import Document
from pptx import Presentation
from pypdf import PdfReader



def extract_text_from_file(file_path):
    """
    يحدد نوع الملف ويستخرج النص المناسب
    """
    ext = os.path.splitext(file_path)[1].lower()

   

    if ext == ".txt":
        return extract_text_from_txt(file_path)
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)

    elif ext == ".docx":
        return extract_text_from_docx(file_path)

    elif ext == ".pptx":
        return extract_text_from_pptx(file_path)

    else:
        raise ValueError(f"Unsupported file type: {ext}")


def extract_text_from_txt(file_path):
    """
    استخراج النص من ملفات TXT
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_text_from_docx(file_path):
    """
    استخراج النص من ملفات DOCX
    """
    doc = Document(file_path)

    full_text = []

    for para in doc.paragraphs:
        full_text.append(para.text)

    return "\n".join(full_text)


def extract_text_from_pptx(file_path):
    """
    استخراج النص من ملفات PowerPoint
    """
    prs = Presentation(file_path)

    full_text = []

    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                full_text.append(shape.text)

    return "\n".join(full_text)


def extract_text_from_pdf(file_path):
    """
    استخراج النص من ملفات PDF
    """
    reader = PdfReader(file_path)

    full_text = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text.append(text)

    return "\n".join(full_text)
