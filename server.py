from fastapi import FastAPI, Form, HTTPException, File, UploadFile
from fastapi import Request
import fastapi
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from fastapi.responses import FileResponse
import openpyxl
import tempfile
import os
import img2pdf
from datetime import datetime, timedelta
from typing import Dict, Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
import jwt
import json

USERS_FILE = "users.json"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

# Директория для сохранения загруженных файлов
upload_dir = "uploaded_files"

# Директория для временных PDF-файлов
pdf_dir = "pdf_files"

# Создаем директорию, если она не существует
if not os.path.exists(upload_dir):
    os.mkdir(upload_dir)

# Создаем директорию, если она не существует
if not os.path.exists(pdf_dir):
    os.mkdir(pdf_dir)

active_tokens = {}
app = FastAPI()
templates = Jinja2Templates(directory="templates")


def get_password_hash(password):
    return password


def load_users() -> dict:
    with open(USERS_FILE, "r", encoding="UTF-8") as f:
        return json.load(f)


def save_users(users_to_save: dict) -> None:
    with open(USERS_FILE, "w", encoding="UTF-8") as f:
        return json.dump(users_to_save, f, ensure_ascii=False)


users: Dict[str, dict] = load_users()


class RegistrationData(BaseModel):
    fullName: str
    email: str
    parentEmail: str
    school: str
    entryYear: int
    birthDate: str
    password: str


class LoginData(BaseModel):
    birthDate: str
    fullName: str
    password: str


class User(BaseModel):
    fullName: str
    email: str
    parentEmail: str
    school: str
    entryYear: int
    birthDate: str


def form_user_key(user_data: RegistrationData | LoginData | User) -> str:
    return user_data.fullName.lower().replace(" ", "").replace(
        "ё", "е"
    ) + user_data.birthDate.replace(".", "")


@app.get("/registration")
async def registration_form(request: Request):
    data = {}
    return templates.TemplateResponse(
        "registration.html", {"request": request, "data": data}
    )


# Эндпоинт для отображения HTML-страницы входа
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    data = {}
    return templates.TemplateResponse("login.html", {"request": request, "data": data})


@app.get("/send_docs")
async def send_docs_form(request: Request):
    data = {"message": "Заполните форму регистрации"}
    return templates.TemplateResponse(
        "send_docs.html", {"request": request, "data": data}
    )


@app.post("/send_docs")
async def upload_files(
    files: list[UploadFile] = File(...), additional_data: str = Form(...)
):
    uploaded_files = []

    # Сохраняем каждый файл на сервере
    for uploaded_file in files:
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        file_path = os.path.join(upload_dir, uploaded_file.filename)
        with open(file_path, "wb") as file:
            file.write(uploaded_file.file.read())
        uploaded_files.append(file_path)

    # Создаем PDF-документ и объединяем файлы
    pdf_filename = os.path.join(pdf_dir, "combined.pdf")

    with open(pdf_filename, "wb") as pdf_file:
        pdf_file.write(img2pdf.convert(uploaded_files))

    return FileResponse(pdf_filename, media_type="application/pdf")


@app.post("/registration")
async def register(data: RegistrationData):
    # Генерируйте ключ на основе ФИО и даты рождения без пробелов
    key = form_user_key(data)
    print(key, data)

    users[key] = data.dict()

    save_users(users)

    return data


@app.get("/download")
async def download_data():
    # Создайте Excel-файл с данными о всех учениках
    workbook = openpyxl.Workbook()
    worksheet = workbook.active

    # Создайте заголовок на основе полей модели RegistrationData
    headers = list(RegistrationData.__annotations__.keys())
    worksheet.append(headers)

    for data in users.values():
        worksheet.append([data[field] for field in headers])

    # Создайте временный файл для сохранения XLSX-файла
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmpfile:
        file_path = tmpfile.name
        workbook.save(file_path)

    # Отправьте файл в HTTP-ответе
    response = FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response.headers["Content-Disposition"] = "attachment; filename=users.xlsx"

    return response


# Функция для проверки токена
def resolve_user_by_token(token) -> dict[str, str]:
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if token not in active_tokens:
        raise HTTPException(status_code=401, detail="Invalid token")

    userkey, creation_time = active_tokens.get(token)

    # Проверка срока действия токена
    current_time = datetime.now()
    token_lifetime = current_time - creation_time
    if token_lifetime.total_seconds() > ACCESS_TOKEN_EXPIRE_MINUTES * 60:
        # Удаляем истекший токен из словаря
        del active_tokens[token]
        raise HTTPException(status_code=401, detail="Invalid token")

    user = users.get(userkey)
    print(userkey)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# Создание токена для аутентификации
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, "SECRET_KEY12345", algorithm="HS256")
    return encoded_jwt


# Функции для аутентификации и авторизации
def verify_password(plain_password, hashed_password):
    return plain_password == hashed_password


# Эндпоинт для создания токена
@app.post("/token")
async def create_token(form_data: LoginData):
    user = users.get(form_user_key(form_data))
    if user is None or not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=400,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=15)
    access_token = create_access_token(
        data={"sub": form_user_key(form_data)}, expires_delta=access_token_expires
    )
    response = fastapi.responses.RedirectResponse(url="/users/me", status_code=302)
    response.set_cookie("access_token", access_token, httponly=True)

    # Сохраняем активный токен в словаре с временем создания
    creation_time = datetime.now()
    active_tokens[access_token] = (form_user_key(form_data), creation_time)

    return response


# Эндпоинт для доступа к данным пользователя
@app.get("/users/me", response_model=User)
async def read_users_me(request: Request):
    access_token = request.cookies.get("access_token")

    try:
        resp = resolve_user_by_token(access_token)
        return resp
    except HTTPException as e:
        return RedirectResponse(url="/login")
