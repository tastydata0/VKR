import shutil
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
from starlette.authentication import requires
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.background import BackgroundTasks
import uvicorn
from docx_generator import generate_doc
import json
from docs_to_pdf import merge_docs_to_pdf
from mail_service import Mail
from fastapi.staticfiles import StaticFiles
from fastapi import status
import src.sheets_api
from models import *
import database
from name_translation import fio_to_genitive
import passwords
import sheets_api
from img2pdf import ImageOpenError

from .middlewares import *
from forms.main_form_fields import form_fields

from application_stages import application_stages

ACCESS_TOKEN_EXPIRE_MINUTES = 15

generated_docs_folder = "data/docx_files"

active_tokens = {}


middleware = [
    Middleware(AuthenticationMiddleware, backend=CookieTokenAuthBackend()),
    Middleware(RedirectMiddleware),
]

app = FastAPI(middleware=middleware)
# app.add_middleware()

app.mount("/static/docs", StaticFiles(directory=generated_docs_folder))
app.mount("/static/html", StaticFiles(directory="data/static/html"))
app.mount("/static/icons", StaticFiles(directory="data/static/icons"))


mail = Mail()
mail_receiver = "alex.zv.ev@gmail.com"
templates = Jinja2Templates(directory="data/static/html")


def form_user_key_dict(user_data: dict) -> str:
    return user_data["fullName"].lower().replace(" ", "").replace("ё", "е") + user_data[
        "birthDate"
    ].replace(".", "")


def form_user_key(user_data: RegistrationData | LoginData | UserBasicData) -> str:
    return form_user_key_dict(user_data.dict())


@app.get("/status", response_class=HTMLResponse)
async def status(request: Request):
    return templates.TemplateResponse(
        "status.html", {"request": request, "application_stages": application_stages}
    )


@app.get("/other")
async def application_status(request: Request):
    return templates.TemplateResponse(
        "base_with_status.html",
        {"request": request, "application_stages": application_stages},
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
@requires("authenticated")
async def send_docs_form(request: Request):
    data = {"message": "Заполните форму регистрации"}
    return templates.TemplateResponse(
        "send_docs.html",
        {
            "request": request,
            "data": data,
            "application_stages": application_stages,
            "user": UserMinInfo(**request.user.dict()),
        },
    )


@app.get("/get_filled_application")
@requires("authenticated")
async def get_filled_application(request: Request, background_tasks: BackgroundTasks):
    filepath = generate_doc(request.user, "application")
    background_tasks.add_task(os.remove, filepath)

    return FileResponse(filepath, filename="Заявление.docx")


@app.get("/get_filled_consent")
@requires("authenticated")
async def get_filled_consent(request: Request, background_tasks: BackgroundTasks):
    filepath = generate_doc(request.user, "consent")
    background_tasks.add_task(os.remove, filepath)

    return FileResponse(filepath, filename="Согласие.docx")


@app.get("/")
@requires("authenticated")
async def get_form(request: Request):
    known_data = request.user.dict()
    if known_data["fullNameGenitive"] is None:
        known_data["fullNameGenitive"] = fio_to_genitive(known_data["fullName"])
    return templates.TemplateResponse(
        "fill_data.html",
        {
            "request": request,
            "form_fields": form_fields,
            "known_data": known_data,
            "programs": sheets_api.load_programs(),
            "application_stages": application_stages,
            "user": UserMinInfo(**request.user.dict()),
        },
    )


@app.post("/")
@requires("authenticated")
async def post_form(request: Request, data: UserBasicData):
    if database.modify_user(request.user.fullName, request.user.birthDate, data) == -1:
        raise HTTPException(status_code=500, detail="Неизвестная ошибка 1")

    if database.modify_user(request.user.fullName, request.user.birthDate, data) == -1:
        raise HTTPException(status_code=500, detail="Неизвестная ошибка 2")

    return RedirectResponse("/send_docs", status_code=302)


@app.post("/send_docs")
@requires("authenticated")
async def upload_files(
    request: Request,
    application_files: list[UploadFile],  # Заявление
    consent_files: list[UploadFile],  # Согласие на обработку данных
    parent_passport_files: list[UploadFile],  # паспорт родителя (1 стр + проп.)
    child_passport_files: list[UploadFile],  # Паспорт ребенка (свидетельство о рожд.)
    parent_snils_files: list[UploadFile],  # Снилс родителя
    child_snils_files: list[UploadFile],  # Снилс ребенка
):
    all_files = (
        application_files
        + consent_files
        + parent_passport_files
        + child_passport_files
        + parent_snils_files
        + child_snils_files
    )

    if (
        len(application_files) == 0
        or len(consent_files) == 0
        or len(parent_passport_files) == 0
        or len(child_passport_files) == 0
        or len(parent_snils_files) == 0
        or len(child_snils_files) == 0
    ):
        raise HTTPException(status_code=400, detail="Не заполнено хотя бы одно поле")

    try:
        pdf_filename = merge_docs_to_pdf(all_files, form_user_key(request.user))
    except ImageOpenError:
        raise HTTPException(status_code=400, detail="Невозможно открыть изображение")

    get_filename = lambda upload_file: upload_file.filename

    # Сохраняем все файлы с названием uuid4
    for f in all_files:
        filename = uuid.uuid4().hex + os.path.splitext(f.filename)[1]
        f.file.seek(0)
        with open(f"data/uploaded_files/{filename}", "wb") as buffer:
            f.filename = buffer.name
            shutil.copyfileobj(f.file, buffer)

    application_documents = ApplicationDocuments(
        applicationFiles=list(map(get_filename, application_files)),
        consentFiles=list(map(get_filename, consent_files)),
        parentPassportFiles=list(map(get_filename, parent_passport_files)),
        childPassportFiles=list(map(get_filename, child_passport_files)),
        parentSnilsFiles=list(map(get_filename, parent_snils_files)),
        childSnilsFiles=list(map(get_filename, child_snils_files)),
    )

    database.update_user_application(
        user_key=UserKey(**request.user.dict()),
        application=Application(documents=application_documents),
    )

    mail.send_pdf_docs(
        mail_receiver, pdf_filename, request.user.parentEmail, request.user.fullName
    )
    return FileResponse(pdf_filename, media_type="application/pdf")


@app.post("/registration")
async def register(data: RegistrationData):
    if not database.register_user(data):
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    return fastapi.responses.RedirectResponse("/login", status_code=302)


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
@app.get("/users/me", response_model=UserBasicData)
@requires("authenticated")
async def read_users_me(request: Request):
    return UserBasicData(**request.user.dict())


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
