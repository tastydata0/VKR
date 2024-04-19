from datetime import datetime
import logging
import pathlib
import uuid
from pymongo import MongoClient
import pandas as pd
import statemachine  # type: ignore
from src.models import *
import dotenv
import os
from src.passwords import get_password_hash, verify_password
from bson import ObjectId
from returns.maybe import Maybe, Nothing, Some, maybe
from returns.pipeline import flow, is_successful
from returns.result import safe
from returns.pointfree import bind
from returns.curry import partial
from lambdas import _
from application_state import ApplicationState

dotenv.load_dotenv(".env")
username = os.getenv("DB_USER")
password = os.getenv("DB_PASS")
auth_source = os.getenv("DB_AUTH_SOURCE")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")

client: MongoClient = MongoClient(
    f"mongodb://{username}:{password}@{db_host}:{db_port}/{auth_source}"
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


def _get_config_raw() -> dict:
    if not config_db.find_one():
        raise ValueError("Конфигурация не найдена")

    return config_db.find_one()  # type: ignore


def get_config() -> Config:
    return Config(**_get_config_raw())


@maybe
def _find_one_maybe(collection, *args, **kwargs) -> dict:
    return collection.find_one(*args, **kwargs)


_find_one_user_maybe = partial(_find_one_maybe, users)


def _find_raw_user(user_id: str) -> Maybe[dict]:
    return _find_one_user_maybe({"_id": ObjectId(user_id)})


def find_user(user_id: str) -> Maybe[User]:
    return _find_raw_user(user_id).bind_optional(lambda raw: User(**raw))


def find_user_by_login_data(login_data: LoginData) -> Maybe[User]:
    return _find_one_user_maybe(
        {"fullName": login_data.fullName, "birthDate": login_data.birthDate}
    ).bind_optional(
        lambda raw: (
            User(**raw)
            if verify_password(password=login_data.password, hash=raw["password"])
            else None
        )
    )


def find_admin_by_login_data(login_data: AdminLoginDto) -> Maybe[AdminWithId]:
    return _find_one_maybe(admins, {"email": login_data.email}).bind_optional(
        lambda raw: (
            AdminWithId(**raw, id=str(raw["_id"]))
            if verify_password(password=login_data.password, hash=raw["password"])
            else None
        )
    )


def find_user_by_full_name(full_name: str) -> Maybe[User]:
    return _find_one_user_maybe({"fullName": full_name}).bind_optional(
        lambda raw: User(**raw)
    )


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


def check_user_password(user_id: str, password: str) -> bool:
    return (
        _find_raw_user(user_id)
        .bind_optional(
            lambda raw: verify_password(password=password, hash=raw["password"])
        )
        .value_or(False)
    )


def update_user_password(user_id: str, password: str):
    users.update_one(
        {"_id": ObjectId(user_id)}, {"$set": {"password": get_password_hash(password)}}
    )


def find_user_creds(user_id: str) -> Maybe[LoginData]:
    return _find_raw_user(user_id).bind_optional(lambda raw: LoginData(**raw))


def find_users_with_status(status: statemachine.State) -> list[User]:
    return [User(**user) for user in users.find({"application.status": status.id})]


def user_exists(user_id: str) -> bool:
    return is_successful(_find_raw_user(user_id))


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


def update_user_application_grade(user_id: str, grade: int):
    return update_user_application_field(user_id, "grade", grade)


def update_user_application_diploma(user_id: str, diploma: bool):
    return update_user_application_field(user_id, "diploma", diploma)


def update_user_application_notify_on_start(user_id: str, notify: bool):
    return update_user_application_field(user_id, "notifyOnStart", notify)


def update_user_application_order(user_id: str, order: str):
    return update_user_application_field(user_id, "order", order)


def update_user_application_documents(user_id: str, documents: ApplicationDocuments):
    # Удаляем старые версии документов

    # TODO сделать через flow?
    old_docs = find_user(user_id).unwrap().application.documents
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


def move_user_application_to_archive(user_id: str):
    user = find_user(user_id)
    if is_successful(user):
        users.update_one(
            {"_id": ObjectId(user_id)},
            {"$push": {"applicationsArchive": user.unwrap().application.dict()}},
            upsert=True,
        )

        users.update_one(
            {"_id": ObjectId(user_id)},
            {"$unset": {"application": None}},
            upsert=True,
        )


def register_user(user_data: RegistrationData) -> Maybe[str]:
    # Хэширование пароля
    user_data_dict = user_data.dict()
    user_data_dict["password"] = get_password_hash(user_data.password)

    return (
        _find_one_maybe(
            users,
            {
                "fullName": user_data_dict["fullName"],
                "birthDate": user_data_dict["birthDate"],
            },
        )
        .bind_optional(lambda x: Nothing)
        .or_else_call(
            lambda: Maybe.from_value(str(users.insert_one(user_data_dict).inserted_id))
        )
    )


def add_auth_token(user_id: str, token: str, role: str = "user"):
    return tokens.insert_one(
        {
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "token": token,
            "role": role,
        }
    )


def find_auth_token(token: str) -> Maybe[dict]:
    return _find_one_maybe(tokens, {"token": token})


@maybe
def find_user_by_token(token: str):
    token_info: Maybe[dict] = find_auth_token(token)
    if token_info.bind_optional(
        lambda token_info: token_info["role"] != "user"
    ).value_or(False):
        return None

    user = token_info.bind(
        lambda token_info: find_user(token_info["user_id"])
    ).value_or(None)

    # TODO ensure and remove
    assert type(user) == User or user is None

    return user


@maybe
def find_admin_by_token(token: str):
    token_info: Maybe[dict] = find_auth_token(token)
    if token_info.bind_optional(
        lambda token_info: token_info["role"] != "admin"
    ).value_or(False):
        return None

    admin = (
        token_info.bind(
            lambda token_info: _find_one_maybe(
                admins, {"_id": ObjectId(token_info["user_id"])}
            )
        )
        .bind_optional(lambda raw: AdminWithId(**raw, id=str(raw["_id"])))
        .value_or(None)
    )

    # TODO ensure and remove
    assert type(admin) == AdminWithId or admin is None

    return admin


# Programs
def validate_program_realization_id_existence(program_id_raw: str) -> bool:
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


def resolve_program_by_realization_id(id: str | None) -> Maybe[dict]:
    return _find_one_maybe(programs, {"confirmed.realizations.id": {"$in": [id]}})


def resolve_program_by_base_id(id: str) -> Maybe[dict]:
    return _find_one_maybe(programs, {"baseId": id})


_setup_db()


def add_program(program: Program) -> None:
    if programs.find_one({"baseId": program.baseId}):
        raise ValueError("Program already exists")

    programs.insert_one(program.dict())


def confirm_program(
    program_base_id: str, confirmed_program: ProgramConfirmedNoId
) -> None:
    program_raw = programs.find_one({"baseId": program_base_id})

    if not program_raw:
        raise ValueError(f"Program {program_base_id} doesn't exist")

    program: Program = Program(**program_raw)

    program.add_confirmed_program(confirmed_program)
    programs.replace_one({"baseId": program_base_id}, program.dict())


def realize_program(
    program_base_id: str, realized_program: ProgramRealizationNoId
) -> None:
    program_raw = programs.find_one({"baseId": program_base_id})

    if not program_raw:
        raise ValueError(f"Program {program_base_id} doesn't exist")

    program: Program = Program(**program_raw)

    program.add_program_realization(realized_program)
    programs.replace_one({"baseId": program_base_id}, program.dict())


def edit_program(program_base_id: str, program: Program) -> bool:
    if programs.find_one({"baseId": program_base_id}) is None:
        raise ValueError("Программы не существует")

    programs.replace_one({"baseId": program_base_id}, program.dict())
    return True


def get_all_discounts() -> list[str]:
    return _get_config_raw()["discounts"]


def are_applications_accepted() -> bool:
    return _get_config_raw().get("acceptApplications", False)


def set_applications_accepted(accepted: bool) -> None:
    config_db.update_one({}, {"$set": {"acceptApplications": accepted}}, upsert=True)


def are_applications_accepted() -> bool:
    return _get_config_raw().get("acceptApplications", False)


def set_applications_accepted(accepted: bool) -> None:
    config_db.update_one({}, {"$set": {"acceptApplications": accepted}}, upsert=True)


def user_count_by_application_state(state: statemachine.State) -> int:
    return users.count_documents({"application.status": state.id})


def get_rejected_by_data_users() -> list[User]:
    return [
        User(**user)
        for user in users.find(
            {
                "$and": [
                    {"application.lastRejectionReason": {"$gte": " "}},
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
    return get_config().teachers


@maybe
def resolve_teacher_by_name(name) -> Teacher:
    for t in get_teachers():
        if t.name == name:
            return t

    return None  # type: ignore


def export_graduate_csv() -> pathlib.Path:
    cursor = users.find(
        {"application.status": ApplicationState.passed.id},
        {"_id": 1, "fullName": 1, "application.teacherName": 1},
    )

    items = [
        {
            "id": user["_id"],
            "fullName": user["fullName"],
            "teacherName": user["application"]["teacherName"],
            "grade": "",
            "diploma": "",
        }
        for user in cursor
    ]

    items.sort(key=lambda x: (x["teacherName"], x["fullName"]))

    output_path = pathlib.Path("/tmp/export_" + uuid.uuid4().hex).with_suffix(".csv")
    pd.DataFrame(items).to_csv(output_path, index=False)
    return output_path
