from uuid import uuid4
from docx import Document
import os
import datetime
from sheets_api import *

from models import User
from name_translation import fio_to_genitive


def generate_doc(userData: User, template_name: str): # template_name: application, consent, ...
    template_file_path = f"data/docx_files/{template_name}.docx"
    filename = f"{uuid4()}.docx"
    output_file_path = f"/tmp/{filename}"

    program_info = list(
        filter(
            lambda program: program["id"] == userData.selectedProgram,
            load_programs(),
        )
    )[0]

    print(filename)

    variables = {
        "{ПРЕДСТАВИТЕЛЬ_ФИО}": userData.parentFullName,  # | "ФИО родителя",
        "{ПРЕДСТАВИТЕЛЬ_АДРЕС}": userData.parentAddress,  # | "Адрес родителя",
        "{РЕБЕНОК_ФИО_РОД_ПАДЕЖ}": fio_to_genitive(
            userData.fullName
        ),  # | "ФИО ребенка",
        "{ПРОГРАММА}": program_info["details"],
        "{ПРОГРАММА_ЧАСЫ}": str(
            int(program_info["hoursAud"]) + int(program_info["hoursHome"])
        ),
        "{ПРОГРАММА_ЧАСЫ_АУД}": str(program_info["hoursAud"]),
        "{РЕБЕНОК_ФИО}": userData.fullName,  # | "ФИО ребенка",
        "{РЕБЕНОК_ДАТА_РОЖ}": userData.birthDate,  # | "Дата рождения ребенка",
        "{РЕБЕНОК_МЕСТО_РОЖ}": userData.birthPlace,  # | "Место рождения ребенка",
        "{РЕБЕНОК_МЕСТО_УЧЕБЫ}": userData.school,  # | "Школа ребенка",
        "{РЕБЕНОК_КЛАСС}": userData.schoolClass,  # | "Класс",
        "{РЕБЕНОК_ТЕЛЕФОН}": userData.phone,  # | "Телефон ребенка",
        "{ПРЕДСТАВИТЕЛЬ_ТЕЛЕФОН}": userData.parentPhone,  # | "Телефон родителя",
        "{ПРЕДСТАВИТЕЛЬ_ПОЧТА}": userData.parentEmail,  # | "Email родителя",
        "{ГОД}": datetime.datetime.now().year,
    }

    template_document = Document(template_file_path)

    for variable_key, variable_value in variables.items():
        for paragraph in template_document.paragraphs:
            replace_text_in_paragraph(paragraph, variable_key, variable_value)

        for table in template_document.tables:
            for col in table.columns:
                for cell in col.cells:
                    for paragraph in cell.paragraphs:
                        replace_text_in_paragraph(
                            paragraph, variable_key, variable_value
                        )

    template_document.save(output_file_path)

    return output_file_path


def replace_text_in_paragraph(paragraph, key, value):
    value = str(value)
    if key in paragraph.text:
        inline = paragraph.runs
        for item in inline:
            if key in item.text:
                item.text = item.text.replace(key, value)
