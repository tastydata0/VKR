from typing import BinaryIO
from models import Document
from cryptography.fernet import Fernet


def save_file_encrypted(filename: str, data: bytes) -> Document:
    key: bytes = Fernet.generate_key()

    fernet = Fernet(key)
    data_encrypted = fernet.encrypt(data)

    with open(filename, "wb") as f:
        f.write(data_encrypted)

    return Document(filename=filename, encryptionKey=key, encryptionVersion=1)


def read_encrypted_document(document: Document) -> bytes:
    if document.encryptionVersion == 0:
        with open(document.filename, "rb") as f:
            return f.read()
    elif document.encryptionVersion == 1:
        fernet = Fernet(document.encryptionKey)
        with open(document.filename, "rb") as f:
            return fernet.decrypt(f.read())
