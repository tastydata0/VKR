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
    status: Optional[str] = Field(None)


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
    application: Application = Field(None)


class UserMinInfo(BaseModel):
    fullName: str


class UserKey(BaseModel):
    # TODO: исправить уязвимость
    fullName: str
    birthDate: str


class Program(BaseModel):
    id: str
    brief: str
    details: str
    hoursAud: int
    hoursHome: int
    iconUrl: str


# class Docs(BaseModel):
#     passportFile: File
#     snilsFile: File
#     certificateFile: File
#     contractFile: File


# Модель данных для полей формы
class FormField(BaseModel):
    id: str
    label: str
    name: str
    type: str = "text"
    placeholder: str
