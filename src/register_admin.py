import src.database as database
import getpass
from src.models import Admin
import src.passwords as passwords


def get_password_twice():
    password = getpass.getpass()
    password2 = getpass.getpass("Repeat password: ")

    while password != password2:
        print("Passwords don't match")
        password = getpass.getpass()
        password2 = getpass.getpass("Repeat password: ")

    return password


if __name__ == "__main__":
    email = input("Email: ")

    password = get_password_twice()
    while not passwords.password_strength_check(password)["password_ok"]:
        print(
            "Password is too weak: 8+ symbols, 1+ number, 1+ uppercase letter, 1+ lowercase letter, 1+ special symbol"
        )
        password = get_password_twice()

    role = input("Role (default=admin): ") or "admin"

    database.upsert_admin(
        Admin(
            email=email,
            password=passwords.get_password_hash(password),
            role=role,
        )
    )
