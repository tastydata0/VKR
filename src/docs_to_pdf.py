import itertools
import os
from typing import List
import uuid
import img2pdf
from models import Document
import io
import PIL
from pdf2image import convert_from_bytes

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

def pdf_bytes_to_jpegs(pdf_bytes: bytes) -> List[bytes]:
    pil_images: List[PIL.Image] = convert_from_bytes(pdf_bytes, fmt="jpeg")
    image_bytearrays = []

    for img in pil_images:
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        image_bytearrays.append(img_byte_arr.getvalue())

    return image_bytearrays

            
for i, img in enumerate(pdf_bytes_to_jpegs(open(path, 'rb').read())):
    with open(f'img_{i}.jpg', 'wb') as f:
        f.write(img)

def document_to_images(doc: Document) -> List[bytes]:
    if os.path.splitext(doc.filename)[1] == 'pdf':
        return pdf_bytes_to_jpegs(doc.read_file())
    else:
        return [pdf_bytes_to_jpegs]

def merge_docs_to_pdf(files: List[Document], file_prefix="") -> Document:
    pdf_filename = os.path.join(pdf_dir, f"{file_prefix}_{uuid.uuid4().hex}.pdf")
    images = itertools.chain(*[document_to_images(doc) for doc in files])

    return Document.save_file(pdf_filename, img2pdf.convert(images))
