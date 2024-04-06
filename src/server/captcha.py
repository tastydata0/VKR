from fast_captcha import img_captcha
from fastapi import HTTPException


captcha_links = {}

MAX_CAPTHCHAS_PER_IP = 20


def create_captcha(client_ip: str):
    img, text = img_captcha()
    captcha_links.setdefault(client_ip, [])
    captcha_links[client_ip].append(text.lower())
    if len(captcha_links[client_ip]) > MAX_CAPTHCHAS_PER_IP:
        captcha_links[client_ip].pop(0)
    print(captcha_links)
    return img


def _check_captcha(client_ip: str, text: str) -> bool:
    if text.lower() in captcha_links.get(client_ip, []):
        captcha_links[client_ip].remove(text.lower())
        return True

    return False


def check_captcha(client_ip: str, text: str) -> None:
    if _check_captcha(client_ip, text):
        return

    raise HTTPException(
        status_code=400,
        detail="Неверно введено сообщение с картинки",
    )