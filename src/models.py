from datetime import date
from typing import Optional
from fastapi import File
from pydantic import BaseModel, Field


class ApplicationStage(BaseModel):
    stageName: str
    stageStatus: str  # current, passed, todo, negative
    stageHref: Optional[str] = Field("#")


class RegistrationData(BaseModel):
    fullName: str
    email: str
    parentEmail: str
    school: str
    schoolClass: int
    birthDate: str
    password: str


class LoginData(BaseModel):
    birthDate: str
    fullName: str
    password: str


class ApplicationDocuments(BaseModel):
    applicationFiles: list[str]
    consentFiles: list[str]
    parentPassportFiles: list[str]
    childPassportFiles: list[str]
    parentSnilsFiles: list[str]
    childSnilsFiles: list[str]


class Application(BaseModel):
    fullName: Optional[str] = Field(
        None
    )  # Полное имя на момент подачи заявления (т.к. может измениться)
    selectedProgram: Optional[str] = Field(None)  # id программы (program-YYYY-MM-DD)
    documents: Optional[ApplicationDocuments] = Field(None)
    status: Optional[str] = Field("filling_info")


class UserBasicData(BaseModel):
    fullName: str
    fullNameGenitive: Optional[str] = Field(None)
    parentFullName: Optional[str] = Field(None)
    parentAddress: Optional[str] = Field(None)
    email: Optional[str] = Field(None)
    parentEmail: str
    school: str
    schoolClass: int
    birthDate: str
    birthPlace: Optional[str] = Field(None)
    phone: Optional[str] = Field(None)
    parentPhone: Optional[str] = Field(None)


class User(UserBasicData):
    application: Application = Field(Application())


class ProgramId(BaseModel):
    baseName: str
    year: int
    month: int
    day: int

    def __str__(self) -> str:
        return f"{self.baseName}-{self.year}-{self.month:<2}-{self.day:<2}"

    @property
    def id(self) -> str:
        return str(self)

    def __lt__(self, other) -> bool:
        return date(self.year, self.month, self.day) < date(
            other.year, other.month, other.day
        )

    @staticmethod
    def from_raw_string(raw_string: str) -> "ProgramId":
        parts = raw_string.split("-")
        return ProgramId(
            baseName=parts[0],
            year=int(parts[1]),
            month=int(parts[2]),
            day=int(parts[3]),
        )


class UserMinInfo(BaseModel):
    fullName: str
    email: str


class UserKey(BaseModel):
    # TODO: исправить уязвимость
    fullName: str
    birthDate: str


class Program(BaseModel):
    id: str
    brief: str  # C++, Python, Java, ...
    details: str
    hoursAud: int
    hoursHome: int
    iconUrl: str
    difficulty: int  # 0, 1, 2, 3
    cost: int


# Модель данных для полей формы
class FormField(BaseModel):
    id: str
    label: str
    name: str
    type: str = "text"
    placeholder: str


import database


class UserFillDataSubmission(UserBasicData):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        database.validate_program_id_existence(kwargs.get("selectedProgram"))

    selectedProgram: str
