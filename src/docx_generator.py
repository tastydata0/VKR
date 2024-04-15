from uuid import uuid4
from docx import Document as DocxDocument
import datetime
from models import *
from name_translation import fio_to_accusative
import database


def generate_doc(
    userData: UserBasicData, template_name: str
):  # template_name: application, consent, ...
    template_file_path = f"data/docx_files/{template_name}.docx"
    filename = f"{uuid4()}.docx"
    output_file_path = f"/tmp/{filename}"

    program_info = Program(
        **database.resolve_program_by_realization_id(
            userData.application.selectedProgram
        )
    )

    print(program_info)

    variables = {
        "{ПРЕДСТАВИТЕЛЬ_ФИО}": userData.parentFullName,  # | "ФИО родителя",
        "{ПРЕДСТАВИТЕЛЬ_АДРЕС}": userData.parentAddress,  # | "Адрес родителя",
        "{РЕБЕНОК_ФИО_РОД_ПАДЕЖ}": fio_to_accusative(
            userData.fullName
        ),  # | "ФИО ребенка",
        "{ПРОГРАММА}": program_info.relevant_confirmed().formalName,
        "{ПРОГРАММА_ЧАСЫ}": str(
            program_info.relevant_confirmed().hoursAud
            + int(program_info.relevant_confirmed().hoursHome)
        ),
        "{ПРОГРАММА_ЧАСЫ_АУД}": str(program_info.relevant_confirmed().hoursAud),
        "{РЕБЕНОК_ФИО}": userData.fullName,  # | "ФИО ребенка",
        "{РЕБЕНОК_ДАТА_РОЖ}": userData.birthDate,  # | "Дата рождения ребенка",
        "{РЕБЕНОК_МЕСТО_РОЖ}": userData.birthPlace,  # | "Место рождения ребенка",
        "{РЕБЕНОК_МЕСТО_УЧЕБЫ}": userData.school,  # | "Школа ребенка",
        "{РЕБЕНОК_КЛАСС}": userData.schoolClass,  # | "Класс",
        "{РЕБЕНОК_ТЕЛЕФОН}": userData.phone,  # | "Телефон ребенка",
        "{ПРЕДСТАВИТЕЛЬ_ТЕЛЕФОН}": userData.parentPhone,  # | "Телефон родителя",
        "{ПРЕДСТАВИТЕЛЬ_ПОЧТА}": userData.parentEmail,  # | "Email родителя",
        "{ГОД}": datetime.now().year,
    }

    template_document = DocxDocument(template_file_path)

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
