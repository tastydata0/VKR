import shutil
import uuid
from fastapi import FastAPI, Form, HTTPException, File, Response, UploadFile
from fastapi import Request
from fastapi.responses import StreamingResponse
import fastapi
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
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
from docs_to_pdf import merge_docs_to_pdf
from mail_service import Mail
from fastapi.staticfiles import StaticFiles
from src import application_state
from src.persistent_model import MongodbPersistentModel
from models import *
import database
from name_translation import fio_to_genitive
import passwords
from img2pdf import ImageOpenError
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter
from slowapi.util import get_remote_address

from .middlewares import *
from .captcha import *
from forms.main_form_fields import form_fields

from application_stages import application_stages

ACCESS_TOKEN_EXPIRE_MINUTES = 15
generated_docs_folder = "data/docx_files"

active_tokens = {}


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Build a simple JSON response that includes the details of the rate limit
    that was hit. If no limit is hit, the countdown is added to headers.
    """
    response = JSONResponse(
        {"detail": f"Слишком много запросов: {exc.detail}"}, status_code=429
    )
    response = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
    return response


middleware = [
    Middleware(AuthenticationMiddleware, backend=CookieTokenAuthBackend()),
    Middleware(RedirectMiddleware),
]

limiter = Limiter(key_func=get_remote_address)
limiter.enabled = False
app = FastAPI(middleware=middleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.mount("/static/docs", StaticFiles(directory=generated_docs_folder))
app.mount("/static/html", StaticFiles(directory="data/static/html"))
app.mount("/static/icons", StaticFiles(directory="data/static/icons"))


mail = Mail()
mail_receiver = "alex.zv.ev@gmail.com"
templates = Jinja2Templates(directory="data/static/html")


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


def redirect_according_to_application_state(
    state: application_state.ApplicationState,
):
    if state.current_state.id == ApplicationState.filling_info.id:
        return RedirectResponse("/application/fill_info")
    elif state.current_state.id == ApplicationState.filling_docs.id:
        return RedirectResponse("/application/fill_docs")
    elif state.current_state.id == ApplicationState.waiting_confirmation.id:
        return RedirectResponse("/application/waiting_confirmation")
    elif state.current_state.id == ApplicationState.approved.id:
        return RedirectResponse("/application/approved")
    else:
        return RedirectResponse("/error")


@app.get("/application")
@requires("authenticated")
async def application_get(request: Request):
    model = MongodbPersistentModel(request.user.id)

    state = application_state.ApplicationState(model=model)

    return redirect_according_to_application_state(state)


@app.get("/application/fill_docs")
@requires("authenticated")
async def send_docs_form(request: Request):
    model = MongodbPersistentModel(
        request.user.id,
    )

    state = application_state.ApplicationState(model=model)

    if state.current_state.id != "filling_docs":
        return redirect_according_to_application_state(state)

    return templates.TemplateResponse(
        "send_docs.html",
        {
            "request": request,
            "application_stages": application_stages,
            "lastRejectionReason": request.user.application.lastRejectionReason,
            "user": UserMinInfo(**request.user.dict()),
        },
    )


@app.get("/get_filled_application")
@limiter.limit("1/minute")
@requires("authenticated")
async def get_filled_application(request: Request, background_tasks: BackgroundTasks):
    filepath = generate_doc(request.user, "application")
    background_tasks.add_task(os.remove, filepath)

    return FileResponse(filepath, filename="Заявление.docx")


@app.get("/get_filled_consent")
@limiter.limit("1/minute")
@requires("authenticated")
async def get_filled_consent(request: Request, background_tasks: BackgroundTasks):
    filepath = generate_doc(request.user, "consent")
    background_tasks.add_task(os.remove, filepath)

    return FileResponse(filepath, filename="Согласие.docx")


@app.get("/application/fill_info")
@requires("authenticated")
async def get_form(request: Request):
    model = MongodbPersistentModel(
        request.user.id,
    )

    state = application_state.ApplicationState(model=model)

    if state.current_state.id not in ("filling_info", "filling_docs"):
        return redirect_according_to_application_state(state)

    known_data = request.user.dict()
    if known_data["fullNameGenitive"] is None:
        known_data["fullNameGenitive"] = fio_to_genitive(known_data["fullName"])

    return templates.TemplateResponse(
        "fill_data.html",
        {
            "request": request,
            "form_fields": form_fields,
            "known_data": known_data,
            "selectedProgram": known_data["application"]["selectedProgram"],
            "lastRejectionReason": known_data["application"]["lastRejectionReason"],
            "programs": database.load_programs(),
            "application_stages": application_stages,
            "user": UserMinInfo(**request.user.dict()),
        },
    )


@app.get("/application/waiting_confirmation")
@requires("authenticated")
async def waiting_confirmation(request: Request):
    model = MongodbPersistentModel(
        request.user.id,
    )

    state = application_state.ApplicationState(model=model)

    if state.current_state.id != "waiting_confirmation":
        return redirect_according_to_application_state(state)

    return templates.TemplateResponse(
        "waiting_confirmation.html",
        {
            "request": request,
            "application_stages": application_stages,
            "user": UserMinInfo(**request.user.dict()),
        },
    )


@app.get("/application/approved")
@requires("authenticated")
async def waiting_confirmation(request: Request):
    model = MongodbPersistentModel(
        request.user.id,
    )

    state = application_state.ApplicationState(model=model)

    if state.current_state.id != "approved":
        return redirect_according_to_application_state(state)

    return templates.TemplateResponse(
        "approved.html",
        {
            "request": request,
            "application_stages": application_stages,
            "user": UserMinInfo(**request.user.dict()),
        },
    )


@app.get("/")
@requires("authenticated")
async def waiting_confirmation(request: Request):
    applicationSelectedProgram = None
    applicationStatus = None
    if request.user.application is not None:
        model = MongodbPersistentModel(
            request.user.id,
        )

        state = application_state.ApplicationState(model=model)
        applicationStatus = state.current_state.name

        print(request.user.application.dict())

        applicationSelectedProgram = request.user.application.dict().get(
            "selectedProgram", None
        )

        if applicationSelectedProgram is not None:
            applicationSelectedProgram = database.resolve_program_by_id(
                applicationSelectedProgram
            )["brief"]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "application_stages": application_stages,
            "user": DashboardUserInfo(
                **request.user.dict(),
                applicationSelectedProgram=applicationSelectedProgram,
                applicationStatus=applicationStatus,
            ),
        },
    )


@app.post("/application/fill_info")
@limiter.limit("1/minute")
@requires("authenticated")
async def post_form(request: Request, data: UserFillDataSubmission):
    model = MongodbPersistentModel(
        request.user.id,
    )

    state = application_state.ApplicationState(model=model)

    if state.current_state.id not in ("filling_info", "filling_docs"):
        return redirect_according_to_application_state(state)

    user_data = UserBasicData(**data.dict())

    if database.modify_user(request.user.id, user_data) == -1:
        raise HTTPException(
            status_code=500,
            detail="Не удалось изменить данные пользователя. Обратитесь к администратору",
        )

    if (
        database.update_user_application_program_id(
            user_id=request.user.id, program_id=data.selectedProgram
        )
        == -1
    ):
        raise HTTPException(
            status_code=500,
            detail="Не удалось обновить заявление. Обратитесь к администратору",
        )

    state.fill_info()

    return RedirectResponse("/application/fill_docs", status_code=302)


@app.post("/application/fill_docs")
@limiter.limit("1/minute")
@requires("authenticated")
async def upload_files(
    request: Request,
    application_files: list[UploadFile],  # Заявление
    consent_files: list[UploadFile],  # Согласие на обработку данных
    parent_passport_files: list[UploadFile],  # паспорт родителя (1 стр + проп.)
    child_passport_files: list[UploadFile],  # Паспорт ребенка (свидетельство о рожд.)
    parent_snils_files: list[UploadFile],  # Снилс родителя
    child_snils_files: list[UploadFile],  # Снилс ребенка
    captcha: str,
):
    check_captcha(request.client.host, captcha)

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

    model = MongodbPersistentModel(
        request.user.id,
    )

    state = application_state.ApplicationState(model=model)

    if state.current_state.id not in ("filling_docs"):
        raise HTTPException(
            status_code=400,
            detail="Нельзя отправлять документы на этапе " + state.current_state.name,
        )

    try:
        pdf_filename = merge_docs_to_pdf(all_files, request.user.id)
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
        applicationFiles=[
            Document(filename=get_filename(f)) for f in application_files
        ],
        consentFiles=[Document(filename=get_filename(f)) for f in consent_files],
        parentPassportFiles=[
            Document(filename=get_filename(f)) for f in parent_passport_files
        ],
        childPassportFiles=[
            Document(filename=get_filename(f)) for f in child_passport_files
        ],
        parentSnilsFiles=[
            Document(filename=get_filename(f)) for f in parent_snils_files
        ],
        childSnilsFiles=[Document(filename=get_filename(f)) for f in child_snils_files],
        mergedPdf=Document(filename=pdf_filename),
    )

    database.update_user_application_documents(
        user_id=request.user.id,
        documents=application_documents,
    )

    state.fill_docs()

    # mail.send_pdf_docs(
    #     mail_receiver, pdf_filename, request.user.parentEmail, request.user.fullName
    # )

    # return FileResponse(pdf_filename, media_type="application/pdf")
    return RedirectResponse("/application/waiting_confirmation", status_code=302)


@app.post("/registration")
@limiter.limit("1/minute")
async def register(request: Request, data: RegistrationData, captcha: str):
    check_captcha(request.client.host, captcha)

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
# )
#     response.headers["Content-Disposition"] = "attachment; filename=users.xlsx"

#     return response


# Эндпоинт для создания токена
@app.post("/token")
async def create_token(form_data: LoginData):
    user = database.find_user_by_login_data(form_data)

    if user is None:
        raise HTTPException(
            status_code=400,
            detail="Неверные данные или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = str(uuid.uuid4())
    database.add_auth_token(user.id, access_token)

    response = fastapi.responses.RedirectResponse(url="/users/me", status_code=302)
    response.set_cookie("access_token", access_token, httponly=True)

    return response


# Эндпоинт для доступа к данным пользователя
@app.get("/users/me")
@requires("authenticated")
async def read_users_me(request: Request):
    return request.user.dict()


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("data/static/favicon.ico")


@app.get("/captcha", summary="captcha", name="captcha")
def get_captcha(request: Request):
    captcha_img = create_captcha(request.client.host)
    return StreamingResponse(content=captcha_img, media_type="image/jpeg")


@app.get("/admin/approve")
async def admin_approve(request: Request):
    return templates.TemplateResponse(
        "admin_approve.html",
        {"request": request, "users": database.find_waiting_users()},
    )


@app.post("/admin/approve")
async def admin_approve(data: AdminApprovalDto):
    print(data)
    # ПО id установить в Application поле lastRejectionReason, если это rejection

    model = MongodbPersistentModel(
        data.userId,
    )

    state = application_state.ApplicationState(model=model)

    if data.status == "approved":
        database.update_user_application_state(
            user_id=data.userId, application_state=ApplicationState.approved.id
        )

        state.approve(database.find_user(data.userId))

    elif data.status == "rejected":
        database.update_user_application_state(
            user_id=data.userId, application_state=ApplicationState.filling_info.id
        )

        database.update_user_application_rejection_reason(
            user_id=data.userId, rejection_reason=data.reason
        )

        state.data_invalid(database.find_user(data.userId))


@app.get("/admin/get_pdf_docs")
async def admin_get_pdf_docs(request: Request, user_id: str):
    return FileResponse(
        database.find_user(user_id).application.documents.mergedPdf,
        media_type="application/pdf",
    )


@app.get("/admin/competition")
async def admin_competition(request: Request):
    return templates.TemplateResponse(
        "admin_competition.html",
        {"request": request, "users": database.find_waiting_users()},
    )


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
