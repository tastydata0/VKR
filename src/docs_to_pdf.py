import os
from typing import List
import img2pdf
from fastapi import UploadFile
import logging
import hashlib

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


def merge_docs_to_pdf(files: List[UploadFile], file_prefix='') -> str:
    uploaded_files = []

    # Сохраняем каждый файл на сервере
    logging.debug("Saving " + str(files))
    all_files_hash = ""
    for uploaded_file in files:
        file_data = uploaded_file.file.read()
        file_hash = hashlib.md5(file_data).hexdigest()
        all_files_hash += file_hash
        file_path = os.path.join(upload_dir, file_prefix + '_' + file_hash)
        with open(file_path, "wb") as file:
            file.write(file_data)
        uploaded_files.append(file_path)

    # Создаем PDF-документ и объединяем файлы
    pdf_filename = os.path.join(
        pdf_dir, f"{file_prefix}_{hashlib.md5(all_files_hash.encode()).hexdigest()}.pdf"
    )

    with open(pdf_filename, "wb") as pdf_file:
        pdf_file.write(img2pdf.convert(uploaded_files))

    return pdf_filename
