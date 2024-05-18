import csv
import json
import uuid
from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi import Request
from fastapi.responses import StreamingResponse
import fastapi
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
import starlette
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.authentication import requires
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
import statemachine  # type: ignore
import uvicorn
from fastapi.staticfiles import StaticFiles
from src.models import *
import src.database as database
from src.name_translation import fio_to_accusative
import src.passwords as passwords
from img2pdf import ImageOpenError  # type: ignore
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.docs_to_pdf import merge_docs_to_pdf
from src.docx_generator import generate_doc
from .middlewares import *
from .captcha import *
from src.forms.main_form_fields import form_fields

from src.application_stages import get_stages_according_to_state
from src.application_state import ApplicationState

from src import application_state, export_docs, schemas
from returns.maybe import Maybe, Nothing, Some
from returns.pipeline import is_successful
from lambdas import _


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

app.mount("/static/icons", StaticFiles(directory="data/static/icons"))
app.mount("/static/dist", StaticFiles(directory="dist"), name="dist")

templates = Jinja2Templates(directory="data/static/html")


def application_stages_by_user_id(user_id):
    return get_stages_according_to_state(
        state=application_state.ApplicationState(user_id=user_id).current_state
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
    return templates.TemplateResponse("registration.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


def redirect_according_to_application_state(
    state: application_state.ApplicationState,
):
    if state.current_state.id == ApplicationState.waiting_for_applications.id:
        return RedirectResponse("/application/waiting_for_applications")
    elif state.current_state.id == ApplicationState.filling_info.id:
        return RedirectResponse("/application/fill_info")
    elif state.current_state.id == ApplicationState.filling_docs.id:
        return RedirectResponse("/application/fill_docs")
    elif state.current_state.id == ApplicationState.waiting_confirmation.id:
        return RedirectResponse("/application/waiting_confirmation")
    elif state.current_state.id == ApplicationState.approved.id:
        return RedirectResponse("/application/approved")
    elif state.current_state.id == ApplicationState.passed.id:
        return RedirectResponse("/application/passed")
    elif state.current_state.id == ApplicationState.not_passed.id:
        return RedirectResponse("/application/not_passed")
    else:
        return RedirectResponse("/error")


@app.get("/application")
@requires("authenticated")
async def application_get(request: Request):
    state = application_state.ApplicationState(request.user.id)

    return redirect_according_to_application_state(state)


@app.get("/application/waiting_for_applications")
@requires("authenticated")
async def waiting_for_applications(request: Request):
    state = ApplicationState(request.user.id)

    state.current_state = state.current_state

    if state.current_state.id != ApplicationState.waiting_for_applications.id:
        return redirect_according_to_application_state(state)

    return templates.TemplateResponse(
        "waiting_for_applications.html",
        {
            "request": request,
            "user": request.user.dict(),
            "application_stages": application_stages_by_user_id(request.user.id),
        },
    )


@app.post("/notify_on_appplications_start")
@requires("authenticated")
async def notify_on_appplications_start(request: Request):
    database.update_user_application_notify_on_start(request.user.id, True)


@app.get("/application/fill_docs")
@requires("authenticated")
async def send_docs_form(request: Request):
    state = application_state.ApplicationState(request.user.id)

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
async def get_filled_application(request: Request):
    return Response(
        content=generate_doc(request.user, "application").getbuffer().tobytes(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/get_filled_consent")
@limiter.limit("1/minute")
@requires("authenticated")
async def get_filled_consent(request: Request):
    return Response(
        content=generate_doc(request.user, "consent").getbuffer().tobytes(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/application/fill_info")
@requires("authenticated")
async def get_form(request: Request):
    state = application_state.ApplicationState(request.user.id)

    if state.current_state.id not in ("filling_info", "filling_docs"):
        return redirect_according_to_application_state(state)

    known_data = request.user.dict()
    if known_data["fullNameGenitive"] is None:
        known_data["fullNameGenitive"] = fio_to_accusative(
            known_data["fullName"]
        ).value_or("")

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
    state = application_state.ApplicationState(request.user.id)

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
async def approved(request: Request):
    state = application_state.ApplicationState(request.user.id)

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
    state = application_state.ApplicationState(request.user.id)

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


@app.get("/application/not_passed")
@requires("authenticated")
async def not_passed(request: Request):
    state = application_state.ApplicationState(request.user.id)

    if state.current_state.id != ApplicationState.not_passed.id:
        return redirect_according_to_application_state(state)

    return templates.TemplateResponse(
        "not_passed.html",
        {
            "request": request,
            "rejectionReason": request.user.application.lastRejectionReason,
            "application_stages": application_stages_by_user_id(request.user.id),
            "user": UserMinInfo(**request.user.dict()),
        },
    )


@app.post("/application/delete_application")
@requires("authenticated")
async def delete_application(request: Request):
    database.move_user_application_to_archive(request.user.id)
    return


@app.get("/")
@requires("authenticated")
async def homepage(request: Request):
    applicationSelectedProgram = None
    applicationStatus = None
    if request.user.application is not None:
        state = application_state.ApplicationState(request.user.id)
        applicationStatus = state.current_state.name

        if request.user.application:
            applicationSelectedProgramId = request.user.application.dict().get(
                "selectedProgram", None
            )
        else:
            applicationSelectedProgramId = None

        if applicationSelectedProgramId is not None:
            applicationSelectedProgram = (
                database.resolve_program_by_realization_id(applicationSelectedProgramId)
                .bind_optional(lambda p: p["brief"])
                .value_or("Неизвестная программа")
            )

        teacher_name = (
            Maybe.from_optional(request.user.application)
            .bind_optional(lambda app: app.dict().get("teacherName", None))
            .value_or(None)
        )

    info = DashboardUserInfo(
        **request.user.dict(),
        applicationSelectedProgram=applicationSelectedProgram,
        applicationStatus=applicationStatus,
        applicationTeacher=database.resolve_teacher_by_name(teacher_name).value_or(
            None
        ),
        completedPrograms=[
            {
                **(
                    database.resolve_program_by_realization_id(
                        application.selectedProgram
                    ).value_or({"brief": "Неизвестная программа"})
                ),
                "year": application.selectedProgram.split("-")[-3],
                "grade": application.grade,
                "diploma": application.diploma,
            }
            for application in request.user.applicationsArchive
            if application.status == ApplicationState.graduated.id
        ],
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "application_stages": application_stages_by_user_id(request.user.id),
            "user": info,
        },
    )


@app.post("/application/fill_info")
@limiter.limit("1/minute")
@requires("authenticated")
async def post_form(request: Request, data: UserFillDataSubmission):
    state = application_state.ApplicationState(request.user.id)

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
    child_passport_files: list[
        UploadFile | str
    ],  # Паспорт обучающегося (свидетельство)
    parent_snils_files: list[UploadFile | str],  # Снилс родителя
    child_snils_files: list[UploadFile | str],  # Снилс обучающегося
    captcha: str,
):
    """
    Поскольку fastapi тут принимает только списком, мы принимаем либо списки UploadFile
    либо список ["use_existing"]. Последний означает, что надо взять ранее загруженный документ.
    """
    check_captcha(request.client.host, captcha)  # type: ignore

    def ensure_field_filled(field):
        if len(field) == 0:
            raise HTTPException(status_code=400, detail="Необходимо загрузить документ")
        elif all(
            (isinstance(elem, starlette.datastructures.UploadFile) for elem in field)
        ):
            pass
        elif field == ["use_existing"]:
            pass
        elif field == ["not_use"]:
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

    state = application_state.ApplicationState(request.user.id)

    if state.current_state.id not in ("filling_docs"):
        raise HTTPException(
            status_code=400,
            detail="Нельзя отправлять документы на этапе " + state.current_state.name,
        )

    def upload_files_to_local_files(
        files: list[UploadFile],
    ) -> list[Document]:
        documents = []
        for file in files:
            if file.file:
                file.file.seek(0)
                filename = os.path.join(
                    "data/uploaded_files",
                    uuid.uuid4().hex + os.path.splitext(file.filename)[1],
                )
                documents.append(Document.save_file(filename, file.file.read()))
        return documents

    if parent_passport_files == ["use_existing"]:
        if (
            request.user.latestDocs is None
            or request.user.latestDocs.parentPassportFiles is None
        ):
            raise HTTPException(
                status_code=400, detail="Необходимо заполнить паспорт родителя"
            )
        parent_passport_local_files = request.user.latestDocs.parentPassportFiles
    elif parent_passport_files == ["not_use"]:
        parent_passport_local_files = None
    else:
        parent_passport_local_files = upload_files_to_local_files(parent_passport_files)

    if child_passport_files == ["use_existing"]:
        if (
            request.user.latestDocs is None
            or request.user.latestDocs.childPassportFiles is None
        ):
            raise HTTPException(
                status_code=400, detail="Необходимо заполнить паспорт обучающегося"
            )
        child_passport_local_files = request.user.latestDocs.childPassportFiles
    else:
        child_passport_local_files = upload_files_to_local_files(child_passport_files)

    if parent_snils_files == ["use_existing"]:
        if (
            request.user.latestDocs is None
            or request.user.latestDocs.parentSnilsFiles is None
        ):
            raise HTTPException(
                status_code=400, detail="Необходимо заполнить СНИЛС родителя"
            )
        parent_snils_local_files = request.user.latestDocs.parentSnilsFiles
    elif parent_snils_files == ["not_use"]:
        parent_snils_local_files = None
    else:
        parent_snils_local_files = upload_files_to_local_files(parent_snils_files)

    if child_snils_files == ["use_existing"]:
        if (
            request.user.latestDocs is None
            or request.user.latestDocs.childSnilsFiles is None
        ):
            raise HTTPException(
                status_code=400, detail="Необходимо заполнить СНИЛС обучающегося"
            )
        child_snils_local_files = request.user.latestDocs.childSnilsFiles
    else:
        child_snils_local_files = upload_files_to_local_files(child_snils_files)

    application_local_files = upload_files_to_local_files(application_files)
    consent_local_files = upload_files_to_local_files(consent_files)

    all_files = (
        application_local_files
        + consent_local_files
        + (parent_passport_local_files or [])
        + child_passport_local_files
        + (parent_snils_local_files or [])
        + child_snils_local_files
    )

    try:
        pdf_document = merge_docs_to_pdf(all_files, request.user.id)
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
        mergedPdf=pdf_document,
    )

    database.update_user_latest_documents(
        user_id=request.user.id,
        documents=personal_documents,
    )

    database.update_user_application_documents(
        user_id=request.user.id,
        documents=application_documents,
    )

    database.update_user_application_rejection_reason(
        user_id=request.user.id,
        rejection_reason=None,
    )

    state.fill_docs()

    return RedirectResponse("/application/waiting_confirmation", status_code=302)


@app.post("/refill_data")
@requires("authenticated")
async def refill_data(request: Request):
    state = application_state.ApplicationState(request.user.id)

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
async def register(request: Request, data: RegistrationDto, captcha: str):
    password_strength = passwords.password_strength_check(data.password)

    if password_strength["length_error"]:
        raise HTTPException(
            status_code=400, detail="Длина пароля должна быть не менее 8 символов"
        )
    if password_strength["uppercase_error"]:
        raise HTTPException(
            status_code=400,
            detail="Пароль должен содержать хотя бы одну заглавную букву",
        )
    if password_strength["lowercase_error"]:
        raise HTTPException(
            status_code=400,
            detail="Пароль должен содержать хотя бы одну строчную букву",
        )
    if password_strength["digit_error"] and password_strength["symbol_error"]:
        raise HTTPException(
            status_code=400,
            detail="Пароль должен содержать хотя бы одну цифру или специальный символ",
        )

    check_captcha(request.client.host, captcha)  # type: ignore

    if not database.register_user(data):
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    return await create_token(LoginData(**data.dict()))


# Эндпоинт для создания токена
@app.post("/token")
async def create_token(form_data: LoginData):
    user = database.find_user_by_login_data(form_data)

    if user == Nothing:
        raise HTTPException(
            status_code=400,
            detail="Неверные данные или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = str(uuid.uuid4())
    database.add_auth_token(user.unwrap().id, access_token)

    response = fastapi.responses.RedirectResponse(url="/", status_code=302)
    response.set_cookie("access_token", access_token, httponly=True)

    return response


@app.post("/logout")
@requires("authenticated")
async def logout(request: Request):
    response = fastapi.responses.RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response


@app.post("/change_password")
@requires("authenticated")
async def change_password(request: Request, data: ChangePasswordDto):
    if database.check_user_password(request.user.id, data.oldPassword) is False:
        raise HTTPException(status_code=400, detail="Неверный пароль")

    database.update_user_password(request.user.id, data.newPassword)
    return "Пароль успешно изменен"


@app.get("/admin/login")
async def login(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})


@app.post("/admin/token")
async def create_admin_token(form_data: AdminLoginDto):
    user = database.find_admin_by_login_data(form_data)

    if user == Nothing:
        raise HTTPException(
            status_code=400,
            detail="Неверные данные или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = str(uuid.uuid4())
    database.add_auth_token(user.unwrap().id, access_token, role="admin")

    response = fastapi.responses.RedirectResponse(
        url="/admin/dashboard", status_code=302
    )
    response.set_cookie("access_token", access_token, httponly=True)

    return response


@app.get("/admin/dashboard")
@requires("admin")
async def admin_dashboard(request: Request):
    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "admin_email": request.user.email,
            "badges": {
                "approve": database.user_count_by_application_state(
                    ApplicationState.waiting_confirmation
                ),
                "competition": database.user_count_by_application_state(
                    ApplicationState.approved
                ),
                "rejected": database.get_rejected_by_data_users_count(),
            },
        },
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("data/static/favicon.ico")


@app.get("/captcha", summary="captcha", name="captcha")
def get_captcha(request: Request):
    captcha_img = create_captcha(request.client.host)
    return StreamingResponse(content=captcha_img, media_type="image/jpeg")


@app.get("/admin/rejected_users_by_docs")
@requires("admin")
async def admin_rejected_users_by_docs(request: Request):
    return templates.TemplateResponse(
        "admin_rejected_users_by_docs.html",
        {
            "request": request,
            "users": database.get_rejected_by_data_users(),
        },
    )


@app.get("/admin/edit_users")
@requires("admin")
async def admin_edit_users(request: Request):
    return templates.TemplateResponse(
        "admin_edit_users.html",
        {
            "request": request,
            "users": database.find_all_users(),
            "teachers": database.get_teachers(),
        },
    )


@app.get("/admin/edit_user")
@requires("admin")
async def admin_edit_user(request: Request, user_id: str):
    return templates.TemplateResponse(
        "admin_edit_user.html",
        {
            "request": request,
            "user": database.find_user(user_id).unwrap(),
            "user_json": database.find_user(user_id).unwrap().json(),
            "user_schema": schemas.user_schema(),
        },
    )


@app.post("/admin/edit_user")
@requires("admin")
async def admin_edit_user_post(request: Request, user_id: str, data: User):
    if not database.user_exists(user_id):
        raise HTTPException(status_code=400, detail="User not found")

    database.modify_user(user_id, UserBasicData(**data.dict()))
    database.update_user_application_discounts(user_id, data.application.discounts)
    database.update_user_application_teacher(user_id, data.application.teacherName)
    database.update_user_application_order(user_id, data.application.order)
    database.update_user_application_state(user_id, data.application.status)
    database.update_user_application_rejection_reason(
        user_id, data.application.lastRejectionReason
    )
    database.update_user_application_program_id(
        user_id, data.application.selectedProgram
    )


@app.post("/admin/set_teacher")
@requires("admin")
async def admin_set_teacher_post(request: Request, data: MultipleSetTeacherDto):
    for user_id in data.usersIds:
        database.update_user_application_teacher(user_id, data.teacherName)
    return


@app.post("/admin/set_order")
@requires("admin")
async def admin_set_order_post(request: Request, data: MultipleSetOrderDto):
    for user_id in data.usersIds:
        database.update_user_application_order(user_id, data.order)
    return


@app.get("/admin/config")
@requires("admin")
async def admin_config(request: Request):
    return templates.TemplateResponse(
        "admin_config.html",
        {
            "request": request,
            "config_json": json.dumps(database.config_db.find_one({}, {"_id": 0})),
            "config_schema": schemas.config_schema(),
        },
    )


@app.post("/admin/edit_config")
@requires("admin")
async def admin_config_post(request: Request, data: Config):
    started_accepting_applications = (
        data.acceptApplications and not database.get_config().acceptApplications
    )
    if started_accepting_applications:
        for user in database.find_users_with_status(
            ApplicationState.waiting_for_applications
        ):
            ApplicationState(user_id=user.id).start_application(True)

    database.config_db.delete_many({})
    database.config_db.insert_one(data.dict())


@app.get("/admin/graduate")
@requires("admin")
async def admin_graduate(request: Request):
    users_without_teachers = [
        u
        for u in database.find_users_with_status(ApplicationState.passed)
        if not u.application.teacherName
    ]
    if users_without_teachers:
        return templates.TemplateResponse(
            "admin_cannot_graduate.html",
            {"request": request, "users": users_without_teachers},
        )
    return templates.TemplateResponse(
        "admin_graduate.html",
        {
            "request": request,
        },
    )


@app.get("/admin/graduate_csv")
@requires("admin")
async def admin_graduate_csv(request: Request):
    return FileResponse(database.export_graduate_csv())


@app.post("/admin/graduate_csv")
@requires("admin")
async def admin_graduate_csv_upload(request: Request, table: UploadFile):
    data = list(csv.DictReader(table.file.read().decode("utf-8-sig").splitlines()))

    for student in data:
        state = application_state.ApplicationState(student["id"])

        if student["grade"] == "0":
            state.not_graduate()
        else:
            state.graduate()

        database.update_user_application_grade(student["id"], int(student["grade"]))
        database.update_user_application_diploma(
            student["id"], student["diploma"].lower() in ("+", "да", "диплом")
        )
        database.move_user_application_to_archive(student["id"])

    return templates.TemplateResponse(
        "admin_graduate.html",
        {
            "request": request,
        },
    )


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
        data.userId,
    )

    try:
        if data.status == "approved":
            state.approve()

        elif data.status == "rejected":
            state.data_invalid()

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
    def check_docs(user: User):
        user_docs = user.application.documents

        if user_docs is None:
            return Response(
                content=f"Пользователь {user.fullName} ({user_id}) не имеет документов.",
                status_code=404,
                media_type="text/plain",
            )

        return Response(
            content=user_docs.mergedPdf.read_file(),
            media_type="application/pdf",
        )

    return database.find_user(user_id).bind_optional(check_docs).unwrap()


@app.get("/admin/export_pdf_docs")
@requires("admin")
async def admin_export_pdf_docs(request: Request, all: int):
    return Response(
        content=export_docs.users_docs_archive(database.find_all_users() if all == 1 else database.find_users_with_status(ApplicationState.passed)), media_type="application/zip"
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

    state = application_state.ApplicationState(data.userId)

    if data.status == "approved":
        state.pass_(database.find_user(data.userId).unwrap())

    elif data.status == "rejected":
        state.not_pass(database.find_user(data.userId).unwrap())

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
            "add_program_schema": AddProgramDto.schema(),
            "confirm_program_schema": schemas.confirm_program_schema(),
            "realize_program_schema": schemas.realize_program_schema(),
            "active_programs_ids": [
                p.baseId for p in database.load_relevant_programs()
            ],
            "active_or_uncompleted_programs_ids": [
                p.baseId for p in database.load_relevant_programs(True, True)
            ],
        },
    )


@app.post("/admin/add_program")
@requires("admin")
async def admin_add_program_post(request: Request, data: AddProgramDto):
    try:
        database.add_program(
            Program(
                **data.dict(),
            )
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Программа уже существует")


@app.post("/admin/confirm_program")
@requires("admin")
async def admin_confirm_program_post(request: Request, data: ConfirmProgramDto):
    database.confirm_program(
        data.id, ProgramConfirmedNoId.from_confirm_program_dto(data)
    )


@app.post("/admin/realize_program")
@requires("admin")
async def admin_realize_program_post(request: Request, data: RealizeProgramDto):
    database.realize_program(
        data.id, ProgramRealizationNoId.from_realize_program_dto(data)
    )


@app.get("/admin/edit_program")
@requires("admin")
async def admin_edit_program(request: Request, program_id: str):
    program: Maybe[Program] = database.resolve_program_by_base_id(
        program_id
    ).bind_optional(lambda x: Program(**x))

    if not is_successful(program):
        raise HTTPException(status_code=404, detail="Программа не найдена")

    return templates.TemplateResponse(
        "admin_edit_programs.html",
        {
            "request": request,
            "program": program.unwrap().dict(),
            "program_json": re.sub(
                r"\b(\d{4})-(\d{2})-(\d{2})T00:00:00\b",
                r"\3.\2.\1",
                program.unwrap().json(),
            ),
            "edit_programs_schema": schemas.edit_programs_schema(),
        },
    )


@app.post("/admin/edit_program")
@requires("admin")
async def admin_edit_program_post(request: Request, program_id: str, data: Program):
    try:
        current_relevant: bool = (
            database.resolve_program_by_base_id(program_id)
            .bind_optional(lambda x: x["relevant"])
            .value_or(False)
        )

        if current_relevant and not data.relevant:
            for user in database.find_all_users():
                if (
                    Maybe.from_optional(user.application.selectedProgram)
                    .bind_optional(lambda x: x.split("-")[0] == program_id)
                    .value_or(False)
                ):
                    user.application.selectedProgram = None
                    database.update_user_application_selected_program(user.id, None)

                    ApplicationState(user.id).program_cancelled()

        database.edit_program(program_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/admin/statistics")
@requires("admin")
async def admin_statistics(request: Request):
    return templates.TemplateResponse(
        "admin_statistics.html",
        {
            "request": request,
        },
    )


@app.get("/admin/statistics_lookup_people")
@requires("admin")
async def admin_statistics_lookup_people(request: Request, people: str):
    full_names_to_lookup = people.splitlines()

    users: list[User] = []
    usersNotFound: list[str] = []

    for full_name in full_names_to_lookup:
        if full_name:
            user = database.find_user_by_full_name(full_name.strip())
            user.bind_optional(users.append)
            user.or_else_call(lambda: usersNotFound.append(full_name))

    users = [user for user in users if user]

    return templates.TemplateResponse(
        "admin_lookup_result.html",
        {"request": request, "users": users, "usersNotFound": usersNotFound},
    )


@app.get("/admin/income")
@requires("admin")
async def admin_income(request: Request):
    users = database.get_users_with_enrollment_order()
    incomes = [
        {
            "program": p.brief,
            "cost": p.relevant_confirmed().cost,
            "studentsCount": len(
                [
                    True
                    for u in users
                    if u.application.selectedProgram == p.relevant_realization().id
                ]
            ),
            "income": sum(
                [
                    p.relevant_confirmed().cost
                    for u in users
                    if u.application.selectedProgram == p.relevant_realization().id
                ]
            ),
        }
        for p in database.load_relevant_programs(True, True)
    ]

    incomes.append(
        {
            "program": "< Все программы >",
            "cost": "",
            "studentsCount": len(users),
            "income": sum([income["income"] for income in incomes]),
        }
    )

    return templates.TemplateResponse(
        "admin_income.html",
        {"request": request, "incomes": incomes},
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
