from email.mime.application import MIMEApplication
import smtplib, ssl
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from random import randint
import dotenv
import os

dotenv.load_dotenv(".env")
mail_username = os.getenv("MAIL_ADDRESS")
mail_password = os.getenv("MAIL_AUTH_TOKEN")
mail_host = os.getenv("MAIL_HOST")


# Класс, реализующий отправку писем с кодом
class Mail:
    def __init__(self):
        # Учетные данные и данные о домене
        self.port = 465
        self.smtp_server_domain_name = mail_host
        self.sender_mail = mail_username
        self.password = mail_password

    # Основной метод, формирующий html и отправляющий пользователю
    def send_pdf_docs(self, receiver, pdf_file_path, sender_email, sender_fullname):
        # Вход
        ssl_context = ssl.create_default_context()
        service = smtplib.SMTP_SSL(
            self.smtp_server_domain_name, self.port, context=ssl_context
        )
        service.login(self.sender_mail, self.password)

        # Ввод данных
        mail = MIMEMultipart("alternative")
        mail["Subject"] = "Подача документов от " + sender_fullname
        mail["To"] = receiver

        # Добавляем информацию о том, кто подал документы
        from_text = f"От: {sender_fullname} <{sender_email}>"
        mail.attach(MIMEText(from_text, "plain"))

        # Прикрепляем PDF-файл
        with open(pdf_file_path, "rb") as pdf_file:
            pdf_attachment = MIMEApplication(pdf_file.read(), _subtype="pdf")
            pdf_attachment.add_header(
                "Content-Disposition", f"attachment; filename={pdf_file_path}"
            )
            mail.attach(pdf_attachment)

        # Отправка
        service.sendmail(self.sender_mail, receiver, mail.as_string())

        # Закрытие сервиса
        service.quit()
