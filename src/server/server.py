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
from typing import Annotated, Dict, List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
import starlette
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.authentication import requires
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.background import BackgroundTasks
import statemachine
import uvicorn
from docx_generator import generate_doc
from docs_to_pdf import merge_docs_to_pdf
from mail_service import Mail
from fastapi.staticfiles import StaticFiles
from src import application_state
from src.persistent_model import MongodbPersistentModel
from models import *
import database
from name_translation import fio_to_accusative
import passwords
from img2pdf import ImageOpenError
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter
from slowapi.util import get_remote_address

from .middlewares import *
from .captcha import *
from forms.main_form_fields import form_fields

from application_stages import get_stages_according_to_state

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
app = FastAPI(middleware=middleware, debug=True)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.mount("/static/docs", StaticFiles(directory=generated_docs_folder))
app.mount("/static/icons", StaticFiles(directory="data/static/icons"))
app.mount("/static/js", StaticFiles(directory="data/static/js"), name="js")

templates = Jinja2Templates(directory="data/static/html")


def application_stages_by_user_id(user_id):
    return get_stages_according_to_state(
        state=application_state.ApplicationState(
            model=MongodbPersistentModel(user_id=user_id)
        ).current_state
    )


@app.get("/status", response_class=HTMLResponse)
async def status(request: Request):
    return templates.TemplateResponse(
        "status.html",
        {
            "request": request,
            "application_stages": application_stages_by_user_id(request.user.id),
        },
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
    elif state.current_state.id == ApplicationState.passed.id:
        return RedirectResponse("/application/passed")
    else:
        return RedirectResponse("/error")


@app.get("/application")
@requires("authenticated")
async def application_get(request: Request):
    state = application_state.ApplicationState(
        model=MongodbPersistentModel(request.user.id)
    )

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
            "application_stages": application_stages_by_user_id(request.user.id),
            "lastRejectionReason": request.user.application.lastRejectionReason,
            "user": UserMinInfo(**request.user.dict()),
            "documents": request.user.latestDocs,
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
        known_data["fullNameGenitive"] = fio_to_accusative(known_data["fullName"])

    print(known_data)

    return templates.TemplateResponse(
        "fill_data.html",
        {
            "request": request,
            "form_fields": form_fields,
            "known_data": known_data,
            "selectedProgram": known_data["application"]["selectedProgram"],
            "lastRejectionReason": known_data["application"]["lastRejectionReason"],
            "programs": [
                AvailableProgram(program).dict()
                for program in database.load_relevant_programs()
            ],
            "application_stages": application_stages_by_user_id(request.user.id),
            "user": UserMinInfo(**request.user.dict()),
            "discounts": database.get_all_discounts(),
            "selectedDiscounts": known_data["application"]["discounts"],
        },
    )


@app.get("/application/waiting_confirmation")
@requires("authenticated")
async def waiting_confirmation(request: Request):
    model = MongodbPersistentModel(
        request.user.id,
    )

    state = application_state.ApplicationState(model=model)

    if state.current_state.id != ApplicationState.waiting_confirmation.id:
        return redirect_according_to_application_state(state)

    return templates.TemplateResponse(
        "waiting_confirmation.html",
        {
            "request": request,
            "application_stages": application_stages_by_user_id(request.user.id),
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

    if state.current_state.id != ApplicationState.approved.id:
        return redirect_according_to_application_state(state)

    return templates.TemplateResponse(
        "approved.html",
        {
            "request": request,
            "application_stages": application_stages_by_user_id(request.user.id),
            "user": UserMinInfo(**request.user.dict()),
        },
    )


@app.get("/application/passed")
@requires("authenticated")
async def passed(request: Request):
    state = application_state.ApplicationState(
        model=MongodbPersistentModel(
            request.user.id,
        )
    )

    if state.current_state.id != ApplicationState.passed.id:
        return redirect_according_to_application_state(state)

    return templates.TemplateResponse(
        "passed.html",
        {
            "request": request,
            "application_stages": application_stages_by_user_id(request.user.id),
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

        applicationSelectedProgram = request.user.application.dict().get(
            "selectedProgram", None
        )

        if applicationSelectedProgram is not None:
            applicationSelectedProgram = database.resolve_program_by_realization_id(
                applicationSelectedProgram
            )["brief"]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "application_stages": application_stages_by_user_id(request.user.id),
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
            detail="Не удалось обновить заявление (программа). Обратитесь к администратору",
        )

    if (
        database.update_user_application_discounts(
            user_id=request.user.id, discounts=data.discounts
        )
        == -1
    ):
        raise HTTPException(
            status_code=500,
            detail="Не удалось обновить заявление (скидки). Обратитесь к администратору",
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
    parent_passport_files: list[UploadFile | str],  # паспорт родителя (1 стр + проп.)
    child_passport_files: list[UploadFile | str],  # Паспорт ребенка (свидетельство)
    parent_snils_files: list[UploadFile | str],  # Снилс родителя
    child_snils_files: list[UploadFile | str],  # Снилс ребенка
    captcha: str,
):
    """
    Поскольку fastapi тут принимает только списком, мы принимаем либо списки UploadFile
    либо список ["use_existing"]. Последний означает, что надо взять ранее загруженный документ.
    """
    check_captcha(request.client.host, captcha)

    def ensure_field_filled(field):
        if len(field) == 0:
            raise HTTPException(status_code=400, detail="Необходимо загрузить документ")
        elif all(
            (isinstance(elem, starlette.datastructures.UploadFile) for elem in field)
        ):
            pass
        elif field == ["use_existing"]:
            pass
        else:
            raise HTTPException(status_code=400, detail="Некорректный тип поля")

    for field in (
        application_files,
        consent_files,
        parent_passport_files,
        child_passport_files,
        parent_snils_files,
        child_snils_files,
    ):
        ensure_field_filled(field)

    state = application_state.ApplicationState(
        model=MongodbPersistentModel(
            request.user.id,
        )
    )

    if state.current_state.id not in ("filling_docs"):
        raise HTTPException(
            status_code=400,
            detail="Нельзя отправлять документы на этапе " + state.current_state.name,
        )

    def save_file(file: UploadFile) -> Document:
        filename = os.path.join(
            "data/uploaded_files", uuid.uuid4().hex + os.path.splitext(file.filename)[1]
        )
        file.file.seek(0)
        with open(filename, "wb") as buffer:
            file.filename = buffer.name
            shutil.copyfileobj(file.file, buffer)

        return Document(filename=filename)

    def upload_files_to_local_files(
        files: list[UploadFile],
    ) -> list[Document]:
        documents = []
        for file in files:
            if file.file:
                documents.append(save_file(file))
        return documents

    if parent_passport_files == ["use_existing"]:
        if (
            request.user.application.documents is None
            or request.user.application.documents.parentPassportFiles is None
        ):
            raise HTTPException(
                status_code=400, detail="Необходимо заполнить паспорт родителя"
            )
        parent_passport_local_files = (
            request.user.application.documents.parentPassportFiles
        )
    else:
        parent_passport_local_files = upload_files_to_local_files(parent_passport_files)

    if child_passport_files == ["use_existing"]:
        if (
            request.user.application.documents is None
            or request.user.application.documents.childPassportFiles is None
        ):
            raise HTTPException(
                status_code=400, detail="Необходимо заполнить паспорт ребенка"
            )
        child_passport_local_files = (
            request.user.application.documents.childPassportFiles
        )
    else:
        child_passport_local_files = upload_files_to_local_files(child_passport_files)

    if parent_snils_files == ["use_existing"]:
        if (
            request.user.application.documents is None
            or request.user.application.documents.parentSnilsFiles is None
        ):
            raise HTTPException(
                status_code=400, detail="Необходимо заполнить СНИЛС родителя"
            )
        parent_snils_local_files = request.user.application.documents.parentSnilsFiles
    else:
        parent_snils_local_files = upload_files_to_local_files(parent_snils_files)

    if child_snils_files == ["use_existing"]:
        if (
            request.user.application.documents is None
            or request.user.application.documents.childSnilsFiles is None
        ):
            raise HTTPException(
                status_code=400, detail="Необходимо заполнить СНИЛС ребенка"
            )
        child_snils_local_files = request.user.application.documents.childSnilsFiles
    else:
        child_snils_local_files = upload_files_to_local_files(child_snils_files)

    application_local_files = upload_files_to_local_files(application_files)
    consent_local_files = upload_files_to_local_files(consent_files)

    all_files = (
        application_local_files
        + consent_local_files
        + parent_passport_local_files
        + child_passport_local_files
        + parent_snils_local_files
        + child_snils_local_files
    )

    try:
        pdf_filename = merge_docs_to_pdf(all_files, request.user.id)
    except ImageOpenError:
        raise HTTPException(status_code=400, detail="Невозможно открыть изображение")

    personal_documents = PersonalDocuments(
        parentPassportFiles=parent_passport_local_files,
        childPassportFiles=child_passport_local_files,
        parentSnilsFiles=parent_snils_local_files,
        childSnilsFiles=child_snils_local_files,
    )

    application_documents = ApplicationDocuments(
        applicationFiles=application_local_files,
        consentFiles=consent_local_files,
        **personal_documents.dict(),
        mergedPdf=Document(filename=pdf_filename),
    )

    database.update_user_latest_documents(
        user_id=request.user.id,
        documents=personal_documents,
    )

    database.update_user_application_documents(
        user_id=request.user.id,
        documents=application_documents,
    )

    state.fill_docs()

    return RedirectResponse("/application/waiting_confirmation", status_code=302)


@app.post("/refill_data")
@requires("authenticated")
async def refill_data(request: Request):
    state = application_state.ApplicationState(
        model=MongodbPersistentModel(request.user.id)
    )

    try:
        state.change_info()
    except statemachine.exceptions.TransitionNotAllowed:
        raise HTTPException(
            status_code=400,
            detail="Нельзя сделать это на этапе: " + state.current_state.name,
        )

    return Response(status_code=200)


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


@app.get("/admin/login")
async def login(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})


@app.post("/admin/token")
async def create_admin_token(form_data: AdminLoginDto):
    user = database.find_admin_by_login_data(form_data)

    if user is None:
        raise HTTPException(
            status_code=400,
            detail="Неверные данные или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = str(uuid.uuid4())
    database.add_auth_token(user.id, access_token, role="admin")

    response = fastapi.responses.RedirectResponse(
        url="/admin/dashboard", status_code=302
    )
    response.set_cookie("access_token", access_token, httponly=True)

    return response


@app.get("/admin/dashboard")
@requires("admin")
async def admin_dashboard(request: Request):
    return templates.TemplateResponse(
        "admin_dashboard.html", {"request": request, "admin_email": request.user.email}
    )


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
@requires("admin")
async def admin_approve(request: Request):
    return templates.TemplateResponse(
        "admin_approve.html",
        {
            "request": request,
            "users": database.find_users_with_status(
                ApplicationState.waiting_confirmation
            ),
        },
    )


@app.post("/admin/approve")
@requires("admin")
async def admin_approve_post(request: Request, data: AdminApprovalDto):
    # ПО id установить в Application поле lastRejectionReason, если это rejection

    state = application_state.ApplicationState(
        model=MongodbPersistentModel(
            data.userId,
        )
    )

    try:
        if data.status == "approved":
            state.approve(database.find_user(data.userId))

        elif data.status == "rejected":
            state.data_invalid(database.find_user(data.userId))

            database.update_user_application_rejection_reason(
                user_id=data.userId, rejection_reason=data.reason
            )
    except statemachine.exceptions.TransitionNotAllowed:
        raise HTTPException(
            status_code=400,
            detail="Не удалось изменить состояние заявки. Скорее всего, ученик только что отозвал заявку. Текущее состояние: "
            + state.current_state.name,
        )


@app.get("/admin/get_pdf_docs")
@requires("admin")
async def admin_get_pdf_docs(request: Request, user_id: str):
    return FileResponse(
        database.find_user(user_id).application.documents.mergedPdf.filename,
        media_type="application/pdf",
    )


@app.get("/admin/competition")
@requires("admin")
async def admin_competition(request: Request):
    return templates.TemplateResponse(
        "admin_competition.html",
        {
            "request": request,
            "users": database.find_users_with_status(ApplicationState.approved),
        },
    )


@app.post("/admin/competition")
@requires("admin")
async def admin_competition_post(request: Request, data: AdminApprovalDto):
    # ПО id установить в Application поле lastRejectionReason, если это rejection

    state = application_state.ApplicationState(
        model=MongodbPersistentModel(
            data.userId,
        )
    )

    if data.status == "approved":
        state.pass_(database.find_user(data.userId))

    elif data.status == "rejected":
        state.not_pass(database.find_user(data.userId))

        database.update_user_application_rejection_reason(
            user_id=data.userId, rejection_reason=data.reason
        )


@app.get("/admin/manage_programs")
@requires("admin")
async def admin_manage_programs(request: Request):
    return templates.TemplateResponse(
        "admin_manage_programs.html",
        {
            "request": request,
            "programs": list(database.programs.find()),
        },
    )


@app.post("/admin/add_program")
@requires("admin")
async def admin_add_program_post(request: Request, data: AddProgramDto):
    try:
        database.add_program(
            Program(
                baseId=data.newProgramId,
                brief=data.newProgramBrief,
                infoHtml=data.newProgramInfoHtml,
                difficulty=data.newProgramDifficulty,
                iconUrl=data.newProgramIconUrl,
            )
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Программа уже существует")


@app.post("/admin/confirm_program")
@requires("admin")
async def admin_confirm_program_post(request: Request, data: ConfirmProgramDto):
    database.confirm_program(
        data.confirmProgramId, ProgramConfirmedNoId.from_confirm_program_dto(data)
    )


@app.post("/admin/realize_program")
@requires("admin")
async def admin_realize_program_post(request: Request, data: RealizeProgramDto):
    database.realize_program(
        data.realizeProgramId, ProgramRealizationNoId.from_realize_program_dto(data)
    )


def register_exception(app: FastAPI):
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
        print(request, exc_str)
        content = {"status_code": 10422, "message": exc_str, "data": None}
        return JSONResponse(content=content, status_code=422)


def start():
    register_exception(app)
    uvicorn.run("server:app", host="127.0.0.1", port=8000, log_level="info")
