from datetime import date
from pydantic import BaseModel, Field
import json
import database


def _date_options() -> dict:
    return {
        "grid_columns": 4,
        "inputAttributes": {
            "placeholder": "Enter date",
        },
        "flatpickr": {
            "inlineHideInput": True,
            "wrap": True,
            "allowInput": True,
            "dateFormat": "d.m.Y",
        },
    }


def confirm_program_schema() -> dict:
    return {
        "title": "Утверждение программы",
        "type": "object",
        "properties": {
            "id": {
                "title": "ID",
                "type": "string",
                "enum": [p.baseId for p in database.load_relevant_programs(True, True)],
            },
            "formalName": {"title": "Официальное название", "type": "string"},
            "cost": {"title": "Стоимость", "minimum": 0, "type": "integer"},
            "hoursAud": {
                "title": "Часы аудиторных занятий",
                "minimum": 0,
                "maximum": 1024,
                "type": "integer",
            },
            "hoursHome": {
                "title": "Часы домашних занятий",
                "minimum": 0,
                "maximum": 1024,
                "type": "integer",
            },
            "confirmDate": {
                "title": "Дата подтверждения",
                "type": "string",
                "format": "date",
                "options": _date_options(),
            },
        },
        "required": [
            "id",
            "formalName",
            "cost",
            "hoursAud",
            "hoursHome",
            "confirmDate",
        ],
    }


def realize_program_schema() -> dict:
    return {
        "title": "Реализация программы",
        "type": "object",
        "properties": {
            "id": {
                "title": "ID",
                "type": "string",
                "enum": [
                    p.baseId for p in database.load_relevant_programs(False, True)
                ],
            },
            "realizeDate": {
                "title": "Дата реализации",
                "type": "string",
                "format": "date",
                "options": _date_options(),
            },
        },
        "required": ["id", "realizeDate"],
    }
