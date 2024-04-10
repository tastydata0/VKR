import os
from typing import List
import uuid
import img2pdf
from models import Document

# Директория для сохранения загруженных файлов
upload_dir = "data/uploaded_files"

# Директория для временных PDF-файлов
pdf_dir = "data/pdf_files"

# Создаем директорию, если она не существует
if not os.path.exists(upload_dir):
    os.mkdir(upload_dir)

# Создаем директорию, если она не существует
if not os.path.exists(pdf_dir):
    os.mkdir(pdf_dir)


def merge_docs_to_pdf(files: List[Document], file_prefix="") -> Document:
    pdf_filename = os.path.join(pdf_dir, f"{file_prefix}_{uuid.uuid4().hex}.pdf")
    images = [doc.read_file() for doc in files]

    return Document.save_file(pdf_filename, img2pdf.convert(images))
