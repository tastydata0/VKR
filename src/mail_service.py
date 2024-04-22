from email.mime.application import MIMEApplication
import logging
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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

    def send_text(self, receiver, subject, text):
        if not receiver:
            return

        ssl_context = ssl.create_default_context()
        service = smtplib.SMTP_SSL(
            self.smtp_server_domain_name, self.port, context=ssl_context
        )
        service.login(self.sender_mail, self.password)

        mail = MIMEMultipart("alternative")
        mail["Subject"] = subject
        mail["To"] = receiver

        mail.attach(MIMEText(text, "html"))

        try:
            service.sendmail(self.sender_mail, receiver, mail.as_string())
        except smtplib.SMTPRecipientsRefused:
            logging.warning("Не удалось отправить письмо на адрес: " + receiver)

        service.quit()

    def notify_of_approval(
        self, receiver, full_name, approved=True, rejection_reason=""
    ):
        if approved:
            self.send_text(
                receiver,
                "Документы в Школу::Кода прошли проверку",
                f"Здравствуйте, {full_name}!<br>"
                + "<h3>Сообщаем вам, что ваши документы на обучение в Школе::Кода прошли проверку!</h3><br>",
            )
        else:
            self.send_text(
                receiver,
                "Документы в Школу::Кода не прошли проверку",
                f"Здравствуйте, {full_name}!<br>"
                + "<h3>Сообщаем вам, что ваши документы на обучение в Школе::Кода не прошли проверку.</h3><br>"
                + f"Причина: {rejection_reason}<br>"
                if rejection_reason
                else ""
                + "Перейдите в личный кабинет, чтобы внести правки в данные или документы",
            )

    def notify_of_passed(self, receiver, full_name, passed=True, rejection_reason=""):
        if passed:
            self.send_text(
                receiver,
                "Зачисление в Школу::Кода ",
                f"Здравствуйте, {full_name}!<br>"
                + "<h3>Сообщаем вам, что заявка на зачисление в Школу::Кода одобрена!</h3><br>",
            )
        else:
            self.send_text(
                receiver,
                "Отказ в зачислении в Школу::Кода",
                f"Здравствуйте, {full_name}!<br>"
                + "<h3>Сообщаем вам, что заявка на зачисление в Школу::Кода не одобрена.</h3><br>"
                + f"Причина: {rejection_reason}<br>"
                if rejection_reason
                else "",
            )

    def notify_on_application_start(self, receiver, full_name):
        self.send_text(
            receiver,
            "Начался прием заявок в Школу:Кода",
            f"Здравствуйте, {full_name}!<br>"
            + "<h3>Сообщаем вам, что прием заявок только что начался!</h3><br>",
        )
