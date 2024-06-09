from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from src.database import find_user_by_token, find_admin_by_token
from returns.maybe import Nothing


class CookieTokenAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if "access_token" not in conn.cookies and "access_token" not in conn.headers:
            return

        token = conn.cookies.get("access_token", conn.headers.get("access_token"))

        user = find_user_by_token(token)
        if user != Nothing:
            return AuthCredentials(["authenticated"]), user.unwrap()

        admin = find_admin_by_token(token)
        if admin != Nothing:
            return AuthCredentials(["admin"]), admin.unwrap()


class RedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.status_code == 403:  # Forbidden
            if "admin" in str(request.url):
                return RedirectResponse("/admin/login")

            return RedirectResponse("/login")
        return response
