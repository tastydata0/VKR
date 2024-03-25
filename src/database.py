from datetime import datetime
import json
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


def update_user_application_documents(user_id: str, documents: ApplicationDocuments):
    return update_user_application_field(user_id, "documents", documents.dict())


def update_user_application_program_id(user_id: str, program_id: str):
    return update_user_application_field(user_id, "selectedProgram", program_id)


def update_user_application_rejection_reason(user_id: str, rejection_reason: str):
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
def validate_program_id_existence(program_id_raw: str) -> None:
    # Проверить, что программа актуальна и что она существует
    query = {"id": program_id_raw, "relevant": True}
    result = programs.find_one(query)
    return result is not None


def load_programs() -> list[dict]:
    return list(programs.find({"relevant": True}, {"_id": 0}))


def resolve_program_by_id(id: str) -> dict:
    return programs.find_one({"id": id}, {"_id": 0})


def _export_users_csv(cursor: Cursor, fields: list[str]) -> pathlib.Path:
    output_path = pathlib.Path("export_" + uuid.uuid4().hex).with_suffix(".csv")
    pd.DataFrame(cursor).to_csv(output_path, columns=fields, index=False)
    return output_path


def export_users_csv(model_name: typing.Type[BaseModel]) -> pathlib.Path:
    cursor = users.find({})
    basic_fields = list(model_name.__fields__.keys())
    return _export_users_csv(cursor, basic_fields)


_setup_db()
