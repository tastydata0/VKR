import zipfile
import io

from src.models import *


def _create_archive(files: dict[str, Document]) -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as f:
        for path, file in files.items():
            f.writestr(path, file.read_file())

    return zip_buffer.getvalue()


def _sanitize_filename(filename: str) -> str:
    return "".join(c if c.isalnum() or c == "." else "_" for c in filename)


def users_docs_archive(users: list[User]) -> bytes:
    files = {
        os.path.join(
            u.application.selectedProgram,
            _sanitize_filename(
                u.application.selectedProgram.split("-")[0] + "_" + u.fullName + ".pdf"
            ),
        ): u.application.documents.mergedPdf
        for u in users
        if u.application.documents and u.application.selectedProgram
    }
    return _create_archive(files)
