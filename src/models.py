from datetime import date, datetime
import re
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field, validator
from application_state import ApplicationState


class Regexes:
    email = re.compile(
        r"([-!#-'*+/-9=?A-Z^-~]+(\.[-!#-'*+/-9=?A-Z^-~]+)*|\"([]!#-[^-~ \t]|(\\[\t -~]))+\")@([-!#-'*+/-9=?A-Z^-~]+(\.[-!#-'*+/-9=?A-Z^-~]+)*|\[[\t -Z^-~]*])"
    )

    birth_date = re.compile(
        r"(^(((0[1-9]|1[0-9]|2[0-8])\.(0[1-9]|1[012]))|((29|30|31)[\/](0[13578]|1[02]))|((29|30)\.(0[4,6,9]|11)))\.(19|[2-9][0-9])\d\d$)|(^29\.02\.(19|[2-9][0-9])(00|04|08|12|16|20|24|28|32|36|40|44|48|52|56|60|64|68|72|76|80|84|88|92|96)$)"
    )

    name = re.compile("[а-яА-Я ]+")


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


class SelectedProgram(BaseModel):
    selectedProgram: Optional[str] = Field(None)

    @validator("selectedProgram")
    @classmethod
    def validate_selected_program(cls, value):
        from database import validate_program_id_existence

        if not validate_program_id_existence(value):
            raise ValueError(f"Программы {value} не существует или она неактуальна")
        return value

    def get_brief_name(self):
        from database import resolve_program_by_id

        return resolve_program_by_id(self.selectedProgram)["brief"]


class Document(BaseModel):
    filename: str
    timestamp: Optional[datetime] = Field(datetime.now().replace(microsecond=0))


class ApplicationDocuments(BaseModel):
    applicationFiles: list[Document]
    consentFiles: list[Document]
    parentPassportFiles: list[Document]
    childPassportFiles: list[Document]
    parentSnilsFiles: list[Document]
    childSnilsFiles: list[Document]
    mergedPdf: Document


class Application(SelectedProgram):
    fullName: Optional[str] = Field(
        None
    )  # Полное имя на момент подачи заявления (т.к. может измениться)
    documents: Optional[ApplicationDocuments] = Field(None)
    status: Optional[str] = Field(
        ApplicationState.filling_docs.id, validate_default=True
    )
    rejectionReason: Optional[str] = Field(None)

    @validator("status")
    @classmethod
    def validate_status(cls, value):
        if not ApplicationState.has_state_by_name(value):
            raise ValueError(f"Статуса заявления {value} не существует")
        return value


class UserMutableData(BaseModel):
    fullNameGenitive: Optional[str] = Field(None)
    parentFullName: Optional[str] = Field(None)
    parentAddress: Optional[str] = Field(None)
    email: Optional[str] = Field(None)
    parentEmail: str
    school: str
    schoolClass: int
    birthPlace: Optional[str] = Field(None)
    phone: Optional[str] = Field(None)
    parentPhone: Optional[str] = Field(None)
    hasLaptop: Optional[bool] = Field(None)

    @validator("email", "parentEmail")
    @classmethod
    def validate_email(cls, value):
        if re.fullmatch(Regexes.email, value) is None:
            raise ValueError("Некорректная почта")
        return value


class UserBasicData(UserMutableData):
    fullName: str
    birthDate: str

    @validator("fullName")
    @classmethod
    def validate_full_name(cls, value):
        if len(value) == 0:
            raise ValueError("Имя не может быть пустым")
        return value

    @validator("birthDate")
    @classmethod
    def validate_birth_date(cls, value):  # 12.04.2003
        if re.fullmatch(Regexes.birth_date, value) is None:
            raise ValueError("Неверный формат даты рождения")
        return value


class AdminApprovalDto(BaseModel):
    userId: str
    status: str
    reason: Optional[str] = None

    @validator("status")
    @classmethod
    def validate_status(cls, value):
        if not value in ("approved", "rejected"):
            raise ValueError(f"Статуса ответ администратора '{value}' не существует")
        return value


class User(UserBasicData):
    def __init__(self, *args, **kwargs):
        if not "id" in kwargs:
            kwargs.setdefault("id", str(kwargs.get("_id")))
        super().__init__(*args, **kwargs)

    id: str
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


class DashboardUserInfo(BaseModel):
    fullName: str
    email: Optional[str] = Field(None)
    parentEmail: str
    school: str
    schoolClass: int
    phone: Optional[str] = Field(None)
    parentPhone: Optional[str] = Field(None)
    applicationSelectedProgram: str | None
    applicationStatus: str | None


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


class UserFillDataSubmission(UserBasicData, SelectedProgram):
    ...
