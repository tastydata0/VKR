import re
from argon2 import PasswordHasher


ph = PasswordHasher()


def get_password_hash(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, hash: str) -> bool:
    try:
        ph.verify(hash=hash, password=password)
        return True
    except:
        return False


def password_strength_check(password: str) -> dict:
    """
    Verify the strength of 'password'
    Returns a dict indicating the wrong criteria
    A password is considered strong if:
        8 characters length or more
        1 digit or more
        1 symbol or more
        1 uppercase letter or more
        1 lowercase letter or more
    """

    length_error = len(password) < 8

    digit_error = re.search(r"\d", password) is None

    uppercase_error = re.search(r"[A-Z]", password) is None

    lowercase_error = re.search(r"[a-z]", password) is None

    symbol_error = re.search(r"\W", password) is None

    password_ok = not ( length_error or digit_error or uppercase_error or lowercase_error or symbol_error )

    return {
        'password_ok' : password_ok,
        'length_error' : length_error,
        'digit_error' : digit_error,
        'uppercase_error' : uppercase_error,
        'lowercase_error' : lowercase_error,
        'symbol_error' : symbol_error,
    }
    