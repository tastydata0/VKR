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


class User(BaseModel):
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
    selectedProgram: Optional[str] = Field(None)
    documents: Optional[dict[str, str]] = Field(
        {"applicationForm": "", "consestToDataProcessing": ""}
    )
    application: Optional[dict[str, str]] = Field(None)


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
