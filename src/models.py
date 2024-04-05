from datetime import date, datetime
import logging
import os
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
    fullName: str = Field(regex=Regexes.name, min_length=1, max_length=100)
    email: str = Field(regex=Regexes.email)
    parentEmail: str
    school: str
    schoolClass: int
    birthDate: str
    password: str


class LoginData(BaseModel):
    birthDate: str
    fullName: str = Field(regex=Regexes.name, min_length=1, max_length=100)
    password: str


class SelectedProgram(BaseModel):
    selectedProgram: Optional[str] = Field(None)

    @validator("selectedProgram")
    @classmethod
    def validate_selected_program(cls, value):
        from database import validate_program_realization_id_existence

        if value is not None and not validate_program_realization_id_existence(value):
            raise ValueError(f"Программы {value} не существует или она неактуальна")
        return value

    def get_brief_name(self):
        from database import resolve_program_by_realization_id

        return resolve_program_by_realization_id(self.selectedProgram)["brief"]


class Document(BaseModel):
    filename: str
    timestamp: Optional[datetime] = Field(datetime.now().replace(microsecond=0))
    encryptionKey: str
    encryptionVersion: int = Field(1)

    @validator("filename")
    @classmethod
    def validate_filename(cls, value):
        if not os.path.exists(value):
            logging.warning(f"Файла {value} не существует")
        return value

    def read_file(self) -> bytes:
        from encryption import read_encrypted_document
        return read_encrypted_document(self)

    @classmethod
    def save_file(cls, filename: str, data: bytes) -> "Document":
        from encryption import save_file_encrypted
        return save_file_encrypted(filename, data)


def files_existence_checker(files: list[Document] | Document):
    for file in files if isinstance(files, list) else [files]:
        if not os.path.exists(file.filename):
            return None

    return files


class PersonalDocuments(BaseModel):
    parentPassportFiles: list[Document]
    childPassportFiles: list[Document]
    parentSnilsFiles: list[Document]
    childSnilsFiles: list[Document]

    @validator(
        "parentPassportFiles",
        "childPassportFiles",
        "parentSnilsFiles",
        "childSnilsFiles",
    )
    @classmethod
    def validate_parent_passport_files(cls, value):
        return files_existence_checker(value)


class ApplicationDocuments(PersonalDocuments):
    applicationFiles: list[Document]
    consentFiles: list[Document]
    mergedPdf: Document

    @validator(
        "applicationFiles",
        "consentFiles",
        "mergedPdf",
    )
    @classmethod
    def validate_application_files(cls, value):
        return files_existence_checker(value)

    @property
    def all_files(self) -> list[Document]:
        files = []
        if self.applicationFiles:
            files += self.applicationFiles
        if self.consentFiles:
            files += self.consentFiles
        if self.mergedPdf:
            files.append(self.mergedPdf)
        if self.parentPassportFiles:
            files += self.parentPassportFiles
        if self.childPassportFiles:
            files += self.childPassportFiles
        if self.parentSnilsFiles:
            files += self.parentSnilsFiles
        if self.childSnilsFiles:
            files += self.childSnilsFiles
        return files


class Application(SelectedProgram):
    fullName: Optional[str] = Field(
        None
    )  # Полное имя на момент подачи заявления (т.к. может измениться)
    documents: Optional[ApplicationDocuments] = Field(None)
    status: Optional[str] = Field(
        ApplicationState.filling_docs.id, validate_default=True
    )
    lastRejectionReason: Optional[str] = Field(None)
    discounts: Optional[list[str]] = Field([])

    @validator("status")
    @classmethod
    def validate_status(cls, value):
        if not ApplicationState.has_state_by_name(value):
            raise ValueError(f"Статуса заявления {value} не существует")
        return value


class UserMutableData(BaseModel):
    fullNameGenitive: Optional[str] = Field(None)
    parentFullName: Optional[str] = Field(
        None, regex=Regexes.name, min_length=1, max_length=100
    )
    parentAddress: Optional[str] = Field(None)
    email: Optional[str] = Field(None, regex=Regexes.email)
    parentEmail: str = Field(regex=Regexes.email)
    school: str
    schoolClass: int
    birthPlace: Optional[str] = Field(None)
    phone: Optional[str] = Field(None)
    parentPhone: Optional[str] = Field(None)
    hasLaptop: Optional[bool] = Field(None)


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
        if Regexes.birth_date.fullmatch(value) is None:
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


class Admin(BaseModel):
    email: str = Field(regex=Regexes.email)
    password: str
    role: str

    @validator("email")
    @classmethod
    def validate_email(cls, value):
        if Regexes.email.fullmatch(value) is None:
            raise ValueError("Некорректная почта")
        return value


class AdminWithId(Admin):
    id: str


class AdminLoginDto(BaseModel):
    email: str
    password: str


class User(UserBasicData):
    def __init__(self, *args, **kwargs):
        if not "id" in kwargs:
            kwargs.setdefault("id", str(kwargs.get("_id")))
        super().__init__(*args, **kwargs)

    id: str
    application: Application = Field(Application())
    latestDocs: Optional[PersonalDocuments] = Field(None)


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


# Модель данных для полей формы
class FormField(BaseModel):
    id: str
    label: str
    name: str
    type: str = "text"
    placeholder: str


class UserFillDataSubmission(UserBasicData, SelectedProgram):
    discounts: Optional[list[str]] = Field([])


"""
Python
    py-2022-09-01
        py-2022-09-01-rel-2022-10-10
        py-2022-09-01-rel-2023-10-10
    py-2024-09-01
"""

DATE_STRFTIME_FORMAT = "%Y-%m-%d"


class ProgramRealizationId(BaseModel):
    id: str = Field(
        regex="[^-]+-[0-9]{4}-[0-9]{2}-[0-9]{2}-rel-[0-9]{4}-[0-9]{2}-[0-9]{2}"
    )


class RealizeProgramDto(BaseModel):
    realizeProgramId: str  # py
    realizeDate: str


class ProgramRealizationNoId(BaseModel):
    realizationDate: datetime = Field(datetime.now().replace(microsecond=0))

    @staticmethod
    def from_realize_program_dto(dto: RealizeProgramDto):
        return ProgramRealizationNoId(
            realizationDate=datetime.strptime(dto.realizeDate, "%d.%m.%Y")
        )


class ProgramRealization(ProgramRealizationNoId, ProgramRealizationId):
    ...


class ConfirmProgramDto(BaseModel):
    confirmProgramId: str  # py
    confirmProgramFormalName: str
    confirmDate: str
    confirmProgramCost: int
    confirmProgramHoursAud: int
    confirmProgramHoursHome: int


# Утвержденная в документах программа
class ProgramConfirmedNoId(BaseModel):
    formalName: str  # Основы программирования на Python
    cost: int
    hoursAud: int
    hoursHome: int
    confirmDate: datetime = Field(datetime.now().replace(microsecond=0))
    realizations: Optional[list[ProgramRealization]] = Field([])

    @staticmethod
    def from_confirm_program_dto(dto: ConfirmProgramDto):
        return ProgramConfirmedNoId(
            formalName=dto.confirmProgramFormalName,
            cost=dto.confirmProgramCost,
            hoursAud=dto.confirmProgramHoursAud,
            hoursHome=dto.confirmProgramHoursHome,
            confirmDate=datetime.strptime(dto.confirmDate, "%d.%m.%Y"),
        )


class ProgramConfirmed(ProgramConfirmedNoId):
    id: str = Field(regex="[^-]+-[0-9]{4}-[0-9]{2}-[0-9]{2}")


class Program(BaseModel):
    baseId: str  # py
    brief: str  # Python
    infoHtml: str  # Основы программирования на Python. Подробнее на <a href="python.org"></a>
    difficulty: int = Field(ge=0, le=3)
    iconUrl: str
    confirmed: list[ProgramConfirmed] = Field([])
    relevant: bool = Field(True)

    def add_confirmed_program(self, program: ProgramConfirmedNoId):
        self.confirmed.append(
            ProgramConfirmed(
                id=f"{self.baseId}-{program.confirmDate.strftime(DATE_STRFTIME_FORMAT)}",
                **program.dict(),
            )
        )

        self.confirmed.sort(key=lambda x: x.confirmDate, reverse=True)

    def add_program_realization(self, realization: ProgramRealizationNoId):
        self.confirmed[0].realizations.append(
            ProgramRealization(
                id=f"{self.confirmed[-1].id}-rel-{realization.realizationDate.strftime(DATE_STRFTIME_FORMAT)}",
                **realization.dict(),
            )
        )

        self.confirmed[0].realizations.sort(
            key=lambda x: x.realizationDate, reverse=True
        )

    def relevant_realization(self) -> ProgramRealization:
        return self.confirmed[0].realizations[0]


class AddProgramDto(BaseModel):
    newProgramId: str
    newProgramBrief: str
    newProgramDifficulty: int
    newProgramInfoHtml: str
    newProgramIconUrl: str


class AvailableProgram(BaseModel):
    def __init__(self, program: Program):
        super().__init__(
            **program.dict(),
            **(program.confirmed[0].dict()),
            lastConfirmedId=program.confirmed[0].id,
            lastRealizationId=program.confirmed[0].realizations[0].id,
        )

    lastConfirmedId: str
    lastRealizationId: str
    brief: str
    infoHtml: str
    difficulty: int = Field(ge=0, le=3)
    iconUrl: str
    formalName: str
    cost: int
    hoursAud: int
    hoursHome: int
