from datetime import date
from pydantic import BaseModel, Field
import json
from src.application_state import ApplicationState
import src.database as database
from src.models import *


def _date_options() -> dict:
    return {
        "grid_columns": 4,
        "inputAttributes": {
            "placeholder": "Дата",
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
                "propertyOrder": 0,
            },
            "realizeDate": {
                "title": "Дата реализации",
                "type": "string",
                "format": "date",
                "options": _date_options(),
                "propertyOrder": 1,
            },
            "finishDate": {
                "title": "Дата завершения программы",
                "type": "string",
                "format": "date",
                "options": _date_options(),
                "propertyOrder": 2,
            },
        },
        "required": ["id", "realizeDate", "finishDate"],
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
                    "diploma": None,
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
                        "enum": [t.name for t in database.get_teachers()] + [""],
                        "default": ""
                    },
                    "order": {"title": "Приказ о зачислении", "type": "string"},
                    "diploma": {
                        "title": "Наличие диплома за лучший результат",
                        "type": "boolean",
                    },
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
            "acceptApplications": {
                "title": "Принимать ли заявки",
                "default": False,
                "type": "boolean"
            },
            "termsUrl": {
                "title": "Ссылка на политику обработки данных сайтом",
                "type": "string"
            }
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


def edit_programs_schema():
    return {
        "title": "Программа",
        "type": "object",
        "properties": {
            "baseId": {
                "title": "Базовый ID",
                "type": "string",
                "readonly": "true",
            },
            "brief": {"title": "Краткое описание", "type": "string"},
            "infoHtml": {"title": "Описание на HTML", "type": "string"},
            "difficulty": {
                "title": "Сложность (0-3)",
                "minimum": 0,
                "maximum": 3,
                "type": "integer",
            },
            "iconUrl": {"title": "URL иконки", "type": "string"},
            "confirmed": {
                "title": "Утвержденные программы",
                "type": "array",
                "items": {"$ref": "#/definitions/ProgramConfirmed"},
            },
            "relevant": {
                "title": "Актуальна ли программа?",
                "default": True,
                "type": "boolean",
            },
        },
        "required": ["baseId", "brief", "infoHtml", "difficulty", "iconUrl"],
        "definitions": {
            "ProgramRealization": {
                "title": "Реализация утвержденной программы",
                "type": "object",
                "properties": {
                    "id": {
                        "title": "Id",
                        "type": "string",
                        "readonly": "true",
                        "propertyOrder": 0,
                    },
                    "realizationDate": {
                        "title": "Дата реализации",
                        "type": "string",
                        "format": "date",
                        "options": _date_options(),
                        "propertyOrder": 1,
                    },
                    "finishDate": {
                        "title": "Дата завершения",
                        "type": "string",
                        "format": "date",
                        "options": _date_options(),
                        "propertyOrder": 2,
                    },
                },
                "required": ["id", "realizationDate", "finishDate"],
            },
            "ProgramConfirmed": {
                "title": "Утвержденная программа",
                "type": "object",
                "properties": {
                    "formalName": {"title": "Формальное название", "type": "string"},
                    "cost": {"title": "Стоимость", "type": "integer"},
                    "hoursAud": {"title": "Аудиторные часы", "type": "integer"},
                    "hoursHome": {
                        "title": "Часы самостоятельной работы",
                        "type": "integer",
                    },
                    "confirmDate": {
                        "title": "Дата утверждения",
                        "type": "string",
                        "format": "date",
                        "options": _date_options(),
                    },
                    "realizations": {
                        "title": "Реализации утвержденной программы",
                        "type": "array",
                        "items": {"$ref": "#/definitions/ProgramRealization"},
                    },
                    "id": {
                        "title": "Id",
                        "type": "string",
                        "readonly": "true",
                    },
                },
                "required": [
                    "formalName",
                    "cost",
                    "hoursAud",
                    "hoursHome",
                    "id",
                ],
            },
        },
    }
