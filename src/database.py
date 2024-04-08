from datetime import datetime
import json
import logging
import pathlib
import typing
import uuid
import pydantic
from pymongo import MongoClient
from pymongo.cursor import Cursor
import pandas as pd
import statemachine
from models import *
import dotenv
import os
from passwords import get_password_hash, verify_password
from bson import ObjectId


dotenv.load_dotenv(".env")
username = os.getenv("DB_USER")
password = os.getenv("DB_PASS")
auth_source = os.getenv("DB_AUTH_SOURCE")

client = MongoClient(
    "mongodb://{}:{}@localhost:27017/{}".format(username, password, auth_source)
)

db = client["codeschool"]
users = db["users"]
tokens = db["tokens"]
programs = db["programs"]
admins = db["admins"]
config_db = db["config"]


def _setup_db():
    try:
        print(tokens.create_index("created_at", expireAfterSeconds=3600))
        print("Индекс создан")
    except Exception as e:
        print("Индекс уже существует")


def _find_user_with_password(user_id: str):
    return users.find_one({"_id": ObjectId(user_id)})


def find_user(user_id: str) -> User | None:
    raw_user_data = _find_user_with_password(user_id)
    if raw_user_data is None:
        return None
    return User(**raw_user_data)


def find_all_users() -> list[User]:
    return [User(**user) for user in users.find({})]


def insert_fake_user(user: User):
    d = user.dict()
    d.pop("id")
    users.insert_one(
        d
        | {
            "password": "$argon2id$v=19$m=65536,t=3,p=4$SW3ifQR2jDFb+JeekGPgUg$N4dp0/bcseuq0X2uwBzad2oZO/HWivg8pTSHkoaAxm4"
        }
    )


def upsert_admin(admin: Admin):
    admins.update_one({"email": admin.email}, {"$set": admin.dict()}, upsert=True)


def find_user_by_login_data(login_data: LoginData) -> User | None:
    raw_user_data = users.find_one(
        {"fullName": login_data.fullName, "birthDate": login_data.birthDate}
    )

    if raw_user_data is None or not verify_password(
        password=login_data.password, hash=raw_user_data["password"]
    ):
        return None

    return User(**raw_user_data)


def find_admin_by_login_data(login_data: AdminLoginDto) -> AdminWithId | None:
    raw_admin_data = admins.find_one({"email": login_data.email})

    if raw_admin_data is None or not verify_password(
        password=login_data.password, hash=raw_admin_data["password"]
    ):
        return None

    return AdminWithId(**raw_admin_data, id=str(raw_admin_data["_id"]))


def find_user_creds(user_id: str) -> LoginData:
    raw_user_data = _find_user_with_password(user_id)
    if raw_user_data is None:
        return None
    return LoginData(**raw_user_data)


def find_users_with_status(status: statemachine.State) -> list[User]:
    return [User(**user) for user in users.find({"application.status": status.id})]


def user_exists(user_id: str) -> bool:
    return _find_user_with_password(user_id) is not None


def modify_user(user_id: str, newUserData: UserBasicData):
    if user_exists(user_id):
        query = {"_id": ObjectId(user_id)}
        new_values = {"$set": newUserData.dict()}
        result = users.update_one(query, new_values)
        return result.modified_count
    else:
        return -1  # Пользователь не существует, модификация невозможна


def update_user_latest_documents(user_id: str, documents: PersonalDocuments):
    if user_exists(user_id):
        query = {"_id": ObjectId(user_id)}
        new_values = {"$set": {"latestDocs": documents.dict()}}
        result = users.update_one(query, new_values)
        return result.modified_count
    else:
        return -1


def update_user_application_field(user_id: str, field: str, value):
    if user_exists(user_id):
        query = {"_id": ObjectId(user_id)}
        new_values = {"$set": {f"application.{field}": value}}
        result = users.update_one(query, new_values)
        return result.modified_count
    else:
        return -1


def update_user_application_state(user_id: str, application_state: str):
    return update_user_application_field(user_id, "status", application_state)


def update_user_application_teacher(user_id: str, teacher_name: str):
    return update_user_application_field(user_id, "teacherName", teacher_name)


def update_user_application_order(user_id: str, order: str):
    return update_user_application_field(user_id, "order", order)


def update_user_application_documents(user_id: str, documents: ApplicationDocuments):
    # Удаляем старые версии документов
    old_docs = find_user(user_id).application.documents
    if old_docs:
        old_files = [file.filename for file in old_docs.all_files]
        current_filenames = [file.filename for file in documents.all_files]
        files_to_delete: list[str] = [
            filename for filename in old_files if filename not in current_filenames
        ]
        for filename in files_to_delete:
            if not os.path.exists(filename):
                logging.warning(
                    f"Файла {filename} не существует. Не удалось удалить старый документ."
                )
                continue
            os.remove(filename)

    return update_user_application_field(user_id, "documents", documents.dict())


def update_user_application_program_id(user_id: str, program_id: str):
    return update_user_application_field(user_id, "selectedProgram", program_id)


def update_user_application_discounts(user_id: str, discounts: list[str]):
    return update_user_application_field(user_id, "discounts", discounts)


def update_user_application_rejection_reason(
    user_id: str, rejection_reason: str | None
):
    return update_user_application_field(
        user_id, "lastRejectionReason", rejection_reason
    )


def register_user(userData: RegistrationData) -> str | None:
    # Хэширование пароля
    userData.password = get_password_hash(userData.password)

    userData = userData.dict()
    if (
        users.find_one(
            {"fullName": userData["fullName"], "birthDate": userData["birthDate"]}
        )
        is None
    ):
        result = users.insert_one(userData)
        return str(result.inserted_id)
    else:
        return None  # Пользователь уже существует


def add_auth_token(user_id: str, token: str, role: str = "user"):
    return tokens.insert_one(
        {
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "token": token,
            "role": role,
        }
    )


def find_auth_token(token: str):
    return tokens.find_one({"token": token})


def find_user_by_token(token: str):
    token_info = find_auth_token(token)
    if token_info is None or token_info["role"] != "user":
        return None
    raw_user_data = users.find_one({"_id": ObjectId(token_info["user_id"])})
    if raw_user_data is None:
        return None
    res = User(**raw_user_data)
    return res


def find_admin_by_token(token: str):
    token_info = find_auth_token(token)
    if token_info is None or token_info["role"] != "admin":
        return None
    raw_admin_data = admins.find_one({"_id": ObjectId(token_info["user_id"])})
    if raw_admin_data is None:
        return None
    res = Admin(**raw_admin_data, id=str(raw_admin_data["_id"]))
    return res


# Programs
def validate_program_realization_id_existence(program_id_raw: str):
    # Проверить, что программа актуальна и что она существует
    query = {"confirmed.realizations.id": {"$in": [program_id_raw]}}
    result = programs.find_one(query)
    return result is not None


def load_relevant_programs(
    load_unconfirmed: bool = False, load_unrealized: bool = False
) -> list[Program]:
    return [
        Program(**program)
        for program in programs.find(
            {"relevant": True}, {"_id": 0}, sort=[("difficulty", 1)]
        )
        if (load_unconfirmed or program["confirmed"])
        and (load_unrealized or program["confirmed"][0]["realizations"])
    ]


def resolve_program_by_realization_id(id: str) -> dict:
    query = {"confirmed.realizations.id": {"$in": [id]}}
    return programs.find_one(query)


def _export_users_csv(cursor: Cursor, fields: list[str]) -> pathlib.Path:
    output_path = pathlib.Path("export_" + uuid.uuid4().hex).with_suffix(".csv")
    pd.DataFrame(cursor).to_csv(output_path, columns=fields, index=False)
    return output_path


def export_users_csv(model_name: typing.Type[BaseModel]) -> pathlib.Path:
    cursor = users.find({})
    basic_fields = list(model_name.__fields__.keys())
    return _export_users_csv(cursor, basic_fields)


_setup_db()


def add_program(program: Program) -> bool:
    if programs.find_one({"baseId": program.baseId}):
        raise ValueError("Program already exists")

    return programs.insert_one(program.dict())


def confirm_program(
    program_base_id: str, confirmed_program: ProgramConfirmedNoId
) -> bool:
    program = programs.find_one({"baseId": program_base_id})

    if not program:
        raise ValueError(f"Program {program_base_id} doesn't exist")

    program: Program = Program(**program)

    program.add_confirmed_program(confirmed_program)
    programs.replace_one({"baseId": program_base_id}, program.dict())

    return


def realize_program(
    program_base_id: str, realized_program: ProgramRealizationNoId
) -> bool:
    program = programs.find_one({"baseId": program_base_id})

    if not program:
        raise ValueError(f"Program {program_base_id} doesn't exist")

    program: Program = Program(**program)

    program.add_program_realization(realized_program)
    programs.replace_one({"baseId": program_base_id}, program.dict())

    return


def get_all_discounts() -> list[str]:
    return config_db.find_one()["discounts"]


def user_count_by_application_state(state: statemachine.State) -> int:
    return users.count_documents({"application.status": state.id})


def get_rejected_by_data_users() -> list[User]:
    return [
        User(**user)
        for user in users.find(
            {
                "$and": [
                    {"application.lastRejectionReason": {"$ne": None}},
                    {
                        "$or": [
                            {"application.status": ApplicationState.filling_info.id},
                            {"application.status": ApplicationState.filling_docs.id},
                        ]
                    },
                ]
            }
        )
    ]


def get_rejected_by_data_users_count() -> int:
    return users.count_documents(
        {
            "$and": [
                {"application.lastRejectionReason": {"$ne": None}},
                {
                    "$or": [
                        {"application.status": ApplicationState.filling_info.id},
                        {"application.status": ApplicationState.filling_docs.id},
                    ]
                },
            ]
        }
    )


def get_teachers() -> list[Teacher]:
    return [Teacher(**teacher) for teacher in config_db.find_one({})["teachers"]]
