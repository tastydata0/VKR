import uuid
from fastapi import FastAPI, Form, HTTPException, File, UploadFile
from fastapi import Request
import fastapi
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
import openpyxl
import tempfile
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
import uvicorn
from docx_generator import generate_doc
import json
from docs_to_pdf import merge_docs_to_pdf
from mail_service import Mail
from fastapi.staticfiles import StaticFiles
from fastapi import status
import sheets_api
from models import *
import database
from name_translation import fio_to_genitive
import passwords

ACCESS_TOKEN_EXPIRE_MINUTES = 15

generated_docs_folder = "data/docx_files"

active_tokens = {}
app = FastAPI()
app.mount("/static/docs", StaticFiles(directory=generated_docs_folder))
app.mount("/static/html", StaticFiles(directory="data/static/html"))


mail = Mail()
mail_receiver = "alex.zv.ev@gmail.com"
templates = Jinja2Templates(directory="data/static/html")


form_fields = [
    FormField(
        id="fullName",
        label="Полное имя",
        name="fullName",
        type="text",
        placeholder="Введите полное имя",
    ),
    FormField(
        id="fullNameGenitive",
        label="Полное имя в родительном падеже. Мы попробовали угадать за вас 😉",
        name="fullNameGenitive",
        type="text",
        placeholder="Введите полное имя в род. падеже",
    ),
    FormField(
        id="parentFullName",
        label="Полное имя родителя",
        name="parentFullName",
        type="text",
        placeholder="Введите полное имя родителя",
        default_value="",
    ),
    FormField(
        id="parentAddress",
        label="Адрес родителя",
        name="parentAddress",
        type="text",
        placeholder="Введите адрес родителя",
        default_value="",
    ),
    FormField(
        id="email",
        label="Email",
        name="email",
        type="email",
        placeholder="example@example.com",
        default_value="",
    ),
    FormField(
        id="parentEmail",
        label="Email родителя",
        name="parentEmail",
        type="email",
        placeholder="parent@example.com",
    ),
    FormField(
        id="school",
        label="Школа",
        name="school",
        type="text",
        placeholder="Введите название школы",
    ),
    FormField(
        id="schoolClass",
        label="Класс",
        name="schoolClass",
        type="number",
        placeholder="Укажите класс",
    ),
    FormField(
        id="birthDate",
        label="Дата рождения",
        name="birthDate",
        type="text",
        placeholder="ДД.ММ.ГГГГ",
    ),
    FormField(
        id="birthPlace",
        label="Место рождения",
        name="birthPlace",
        type="text",
        placeholder="Место рождения",
        default_value="",
    ),
    FormField(
        id="phone",
        label="Ваш телефон",
        name="phone",
        type="text",
        placeholder="Введите ваш номер телефона",
        default_value="",
    ),
    FormField(
        id="parentPhone",
        label="Телефон родителя",
        name="parentPhone",
        type="text",
        placeholder="Введите номер телефона родителя",
        default_value="",
    ),
]


def form_user_key_dict(user_data: dict) -> str:
    return user_data["fullName"].lower().replace(" ", "").replace("ё", "е") + user_data[
        "birthDate"
    ].replace(".", "")


def form_user_key(user_data: RegistrationData | LoginData | User) -> str:
    return form_user_key_dict(user_data.dict())


@app.get("/programs")
async def programs(request: Request):
    return templates.TemplateResponse(
        "programs.html", {"request": request, "programs": sheets_api.load_programs()}
    )


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
    access_token = request.cookies.get("access_token")
    print(f"{access_token=}")

    try:
        data = {"message": "Заполните форму регистрации"}
        return templates.TemplateResponse(
            "send_docs.html", {"request": request, "data": data}
        )
    except HTTPException as e:
        return RedirectResponse(url="/login")


@app.get("/")
async def get_form(request: Request):
    access_token = request.cookies.get("access_token")

    try:
        user = resolve_user_by_token(access_token)

        known_data = user.dict()
        if known_data["fullNameGenitive"] is None:
            known_data["fullNameGenitive"] = fio_to_genitive(known_data["fullName"])
        print(known_data)
        return templates.TemplateResponse(
            "fill_data.html",
            {
                "request": request,
                "form_fields": form_fields,
                "known_data": known_data,
                "programs": sheets_api.load_programs(),
            },
        )

    except HTTPException as e:
        return RedirectResponse(url="/login")


@app.post("/")
async def post_form(request: Request, data: User):
    try:
        user = resolve_user_by_token(request.cookies.get("access_token"))

        database.modify_user(user.fullName, user.birthDate, data)

        result_url = "static/docs/" + generate_doc(data)
        print(result_url)
        return {"url": result_url}

    except HTTPException as e:
        return RedirectResponse(url="/login")


@app.post("/send_docs")
async def upload_files(request: Request, files: list[UploadFile]):
    access_token = request.cookies.get("access_token")

    try:
        user = resolve_user_by_token(access_token)

        pdf_filename = merge_docs_to_pdf(files, form_user_key(user))
        mail.send_pdf_docs(mail_receiver, pdf_filename, user.parentEmail, user.fullName)
        return FileResponse(pdf_filename, media_type="application/pdf")

    except HTTPException as e:
        return RedirectResponse(url="/login")


@app.post("/registration")
async def register(data: RegistrationData):
    if not database.register_user(data):
        raise HTTPException(status_code=400, detail="User exists")

    return fastapi.responses.RedirectResponse(
        "/login", status_code=status.HTTP_302_FOUND
    )


# @app.get("/download")
# async def download_data():
#     # Создаем Excel-файл с данными о всех учениках
#     workbook = openpyxl.Workbook()
#     worksheet = workbook.active

#     # Создаем заголовок на основе полей модели RegistrationData
#     headers = list(RegistrationData.__annotations__.keys())
#     worksheet.append(headers)

#     for data in users.values():
#         worksheet.append([data[field] for field in headers])

#     # Создаем временный файл для сохранения XLSX-файла
#     with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmpfile:
#         file_path = tmpfile.name
#         workbook.save(file_path)

#     # Отправьте файл в HTTP-ответе
#     response = FileResponse(
#         file_path,
#         media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#     )
#     response.headers["Content-Disposition"] = "attachment; filename=users.xlsx"

#     return response


# Функция для проверки токена
def resolve_user_by_token(token: str) -> User:
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user: User = database.find_user_by_token(token)

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user


# Эндпоинт для создания токена
@app.post("/token")
async def create_token(form_data: LoginData):
    user_with_pass = database._find_user_with_password(
        form_data.fullName, form_data.birthDate
    )

    if user_with_pass is None or not passwords.verify_password(
        password=form_data.password, hash=user_with_pass["password"]
    ):
        raise HTTPException(
            status_code=400,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = str(uuid.uuid4())
    database.add_auth_token(
        user_with_pass["fullName"], user_with_pass["birthDate"], access_token
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
        user = resolve_user_by_token(access_token)
        return user
    except HTTPException as e:
        return RedirectResponse(url="/login")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("data/static/favicon.ico")


def register_exception(app: FastAPI):
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
        # or logger.error(f'{exc}')
        print(request, exc_str)
        content = {"status_code": 10422, "message": exc_str, "data": None}
        return JSONResponse(content=content, status_code=422)


def start():
    register_exception(app)
    uvicorn.run("server:app", host="127.0.0.1", port=8000, log_level="info")
