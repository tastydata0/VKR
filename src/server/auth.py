from starlette.applications import Starlette
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
)
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from database import find_user_by_token


class BasicAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if "access_token" not in conn.cookies:
            return

        print("cookies:", conn.cookies)

        # auth = conn.cookies.get("access_token")
        token = conn.cookies.get("access_token")

        user = find_user_by_token(token)

        # try:
        #     scheme, token = auth.split()
        #     if scheme.lower() != "bearer":
        #         return
        # except ValueError as exc:
        #     raise AuthenticationError("Invalid auth credentials")

        return AuthCredentials(["authenticated"]), SimpleUser(user.fullName)


async def homepage(request):
    if request.user.is_authenticated:
        return PlainTextResponse("Hello, " + request.user.display_name)
    return PlainTextResponse("Hello, you")


async def post_test(request):
    return PlainTextResponse("Hello, " + request.user.display_name)


routes = [
    Route("/", endpoint=homepage),
    Route("/post", endpoint=post_test, methods=["POST"]),
]

# app = FastAPI(routes=routes, middleware=middleware)
