from datetime import date
from pydantic import BaseModel, Field
import json
import database
from models import *


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
                "propertyOrder": 1,
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


def user_schema():
    return {
        "title": "Пользователь",
        "type": "object",
        "properties": {
            "fullName": {
                "title": "Полное имя",
                "type": "string",
                "propertyOrder": 100,
            },
            "fullNameGenitive": {
                "title": "Полное имя (винительный)",
                "type": "string",
                "propertyOrder": 200,
            },
            "birthDate": {
                "title": "Дата рождения",
                "type": "string",
                "propertyOrder": 300,
            },
            "email": {
                "title": "Электронная почта",
                "type": "string",
                "propertyOrder": 400,
            },
            "parentEmail": {
                "title": "Электронная почта родителя",
                "type": "string",
                "propertyOrder": 500,
            },
            "parentFullName": {
                "title": "Полное имя родителя",
                "type": "string",
                "maxLength": 100,
                "minLength": 1,
                "pattern": "[а-яА-Я ]+",
                "propertyOrder": 600,
            },
            "parentAddress": {
                "title": "Адрес родителя",
                "type": "string",
                "propertyOrder": 700,
            },
            "birthPlace": {
                "title": "Место рождения",
                "type": "string",
                "propertyOrder": 800,
            },
            "school": {"title": "Школа", "type": "string", "propertyOrder": 600},
            "schoolClass": {
                "title": "Класс школы",
                "type": "integer",
                "propertyOrder": 900,
            },
            "phone": {"title": "Телефон", "type": "string", "propertyOrder": 900},
            "parentPhone": {
                "title": "Телефон родителя",
                "type": "string",
                "propertyOrder": 1000,
            },
            "hasLaptop": {
                "title": "Есть ноутбук",
                "type": "boolean",
                "propertyOrder": 1100,
            },
            "application": {
                "title": "Заявление",
                "propertyOrder": 1200,
                "default": {
                    "selectedProgram": None,
                    "fullName": None,
                    "documents": None,
                    "status": "filling_docs",
                    "lastRejectionReason": None,
                    "discounts": [],
                    "teacherName": None,
                    "order": None,
                },
                "allOf": [{"$ref": "#/definitions/Application"}],
            },
        },
        "required": ["parentEmail", "school", "schoolClass", "fullName", "birthDate"],
        "definitions": {
            "Application": {
                "title": "Заявление",
                "type": "object",
                "properties": {
                    "selectedProgram": {
                        "title": "Выбранная программа",
                        "type": "string",
                        "enum": [
                            p.confirmed[0].realizations[0].id
                            for p in database.load_relevant_programs(False, False)
                        ],
                    },
                    "fullName": {"title": "Полное имя", "type": "string"},
                    "status": {
                        "title": "Статус",
                        "type": "string",
                        "enum": [s.id for s in ApplicationState.states],
                    },
                    "lastRejectionReason": {
                        "title": "Причина последнего отказа",
                        "type": "string",
                    },
                    "discounts": {
                        "title": "Льготы",
                        "type": "array",
                        "propertyOrder": 9999,
                        "items": {
                            "type": "string",
                            "enum": [
                                discount["id"]
                                for discount in database.get_all_discounts()
                            ],
                        },
                    },
                    "teacherName": {
                        "title": "Имя учителя",
                        "type": "string",
                        "enum": [t.name for t in database.get_teachers()],
                    },
                    "order": {"title": "Приказ о зачислении", "type": "string"},
                },
            }
        },
    }


def config_schema():
    return {
        "title": "Настройки",
        "type": "object",
        "properties": {
            "teachers": {
                "title": "Преподаватели",
                "default": [],
                "type": "array",
                "items": {"$ref": "#/definitions/Teacher"},
            },
            "discounts": {
                "title": "Льготы",
                "default": [],
                "type": "array",
                "items": {"$ref": "#/definitions/Discount"},
            },
        },
        "definitions": {
            "Teacher": {
                "title": "Преподаватель",
                "type": "object",
                "properties": {
                    "name": {
                        "title": "ФИО преподавателя",
                        "minLength": 1,
                        "type": "string",
                    },
                    "auditory": {
                        "title": "Аудитория проведения занятий",
                        "minLength": 1,
                        "type": "string",
                    },
                    "schedule": {
                        "title": "Расписание занятий",
                        "description": "Поддерживается HTML",
                        "minLength": 1,
                        "type": "string",
                    },
                    "relevantVkGroupUrl": {
                        "title": "Ссылка на актуальную группу ВК",
                        "type": "string",
                    },
                    "relevantDiscordUrl": {
                        "title": "Ссылка на актуальный сервер Discord",
                        "type": "string",
                    },
                    "relevantJournalUrl": {
                        "title": "Ссылка на актуальный журнал",
                        "type": "string",
                    },
                },
                "required": ["name"],
            },
            "Discount": {
                "title": "Льгота",
                "type": "object",
                "properties": {
                    "id": {"title": "ID", "minLength": 1, "type": "string"},
                    "desc": {"title": "Описание", "minLength": 1, "type": "string"},
                },
                "required": ["id", "desc"],
            },
        },
    }
