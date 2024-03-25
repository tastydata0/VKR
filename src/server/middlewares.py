from starlette.applications import Starlette
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
)
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.responses import PlainTextResponse, RedirectResponse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from database import find_user_by_token, find_admin_by_token


class CookieTokenAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if "access_token" not in conn.cookies:
            return

        token = conn.cookies.get("access_token")

        user = find_user_by_token(token)
        if user is not None:
            return AuthCredentials(["authenticated"]), user

        admin = find_admin_by_token(token)
        if admin is not None:
            return AuthCredentials(["admin"]), admin


class RedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.status_code == 403:  # Forbidden
            if "admin" in request.url:
                return RedirectResponse("/admin/login")

            return RedirectResponse("/login")
        return response
