from datetime import datetime
import json
from pymongo import MongoClient
from models import *
import dotenv
import os
from passwords import get_password_hash

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


def _setup_db():
    try:
        print(tokens.create_index("created_at", expireAfterSeconds=3600))
        print("Индекс создан")
    except Exception as e:
        print("Индекс уже существует")


def _find_user_with_password(fullName: str, birthDate: str):
    return users.find_one({"fullName": fullName, "birthDate": birthDate})


def find_user(fullName: str, birthDate: str) -> User | None:
    raw_user_data = _find_user_with_password(fullName=fullName, birthDate=birthDate)
    if raw_user_data is None:
        return None
    return User(**raw_user_data)


def find_user_creds(fullName: str, birthDate: str) -> LoginData:
    raw_user_data = _find_user_with_password(fullName=fullName, birthDate=birthDate)
    if raw_user_data is None:
        return None
    return LoginData(**raw_user_data)


def user_exists(fullName: str, birthDate: str):
    user = find_user(fullName, birthDate)
    return user is not None


def modify_user(fullName: str, birthDate: str, newUserData: UserBasicData):
    if user_exists(fullName, birthDate):
        query = {"fullName": fullName, "birthDate": birthDate}
        new_values = {"$set": newUserData.dict()}
        result = users.update_one(query, new_values)
        return result.modified_count
    else:
        return -1  # Пользователь не существует, модификация невозможна


def update_user_application(user_key: UserKey, application: Application):
    if user_exists(user_key.fullName, user_key.birthDate):
        query = {"fullName": user_key.fullName, "birthDate": user_key.birthDate}
        new_values = {"$set": {"application": application.dict()}}
        result = users.update_one(query, new_values)
        return result.modified_count
    else:
        return -1


def update_user_application_state(user_key: UserKey, application_state: str):
    if user_exists(user_key.fullName, user_key.birthDate):
        query = {"fullName": user_key.fullName, "birthDate": user_key.birthDate}
        new_values = {"$set": {"application": {"state": application_state}}}
        result = users.update_one(query, new_values)
        return result.modified_count
    else:
        return -1


def register_user(userData: RegistrationData):
    # Хэширование пароля
    userData.password = get_password_hash(userData.password)

    userData = userData.dict()
    if not user_exists(userData["fullName"], userData["birthDate"]):
        result = users.insert_one(userData)
        return result.inserted_id
    else:
        return None  # Пользователь уже существует


def add_auth_token(fullName: str, birthDate: str, token: str):
    raw_user_data = _find_user_with_password(fullName, birthDate)
    user_id = raw_user_data["_id"]
    return tokens.insert_one(
        {"user_id": user_id, "created_at": datetime.utcnow(), "token": token}
    )


def find_auth_token(token: str):
    return tokens.find_one({"token": token})


def find_user_by_token(token: str):
    token_info = find_auth_token(token)
    if token_info is None:
        return None
    raw_user_data = users.find_one({"_id": token_info["user_id"]})
    if raw_user_data is None:
        return None
    return User(**raw_user_data)


_setup_db()
