from io import BytesIO
from docx import Document as DocxDocument
import datetime
from models import *
from name_translation import fio_to_accusative
import database


def format_date(date: date | datetime) -> str:
    months = [
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    ]

    day = date.day
    month = months[date.month - 1]
    year = date.year
    formatted_date = f"{day:02d} {month} {year} г."
    return formatted_date


def generate_doc(
    userData: UserBasicData, template_name: str
) -> BytesIO:  # template_name: application, consent, ...
    template_file_path = f"data/docx_files/{template_name}.docx"

    program_info = Program(
        **database.resolve_program_by_realization_id(
            userData.application.selectedProgram
        )
    )

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
        "{ПРОГРАММА_НАЧАЛО}": format_date(
            program_info.relevant_realization().realizationDate
        ),
        "{ПРОГРАММА_КОНЕЦ}": format_date(
            program_info.relevant_realization().finishDate
        ),
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

    docx_bytes = BytesIO()

    template_document.save(docx_bytes)

    return docx_bytes


def replace_text_in_paragraph(paragraph, key, value):
    value = str(value)
    if key in paragraph.text:
        inline = paragraph.runs
        for item in inline:
            if key in item.text:
                item.text = item.text.replace(key, value)
