from statemachine import StateMachine, State  # type: ignore
from src.mail_service import Mail
from src.persistent_model import MongodbPersistentModel

mail = Mail()


class ApplicationState(StateMachine):
    waiting_for_applications = State("Ожидание начала сбора заявлений", initial=True)
    filling_info = State("Ввод данных и выбор программы")
    filling_docs = State("Загрузка документов")
    waiting_confirmation = State("Ожидание подтверждения")
    approved = State("Заявление принято")
    not_passed = State("Не прошел конкурс на программу")
    passed = State("Зачислен на программу")
    graduated = State("Программа пройдена", final=True)

    def __init__(self, user_id: str):
        StateMachine.__init__(self, model=MongodbPersistentModel(user_id=user_id))
        self.user_id = user_id

        if self.current_state == ApplicationState.waiting_for_applications:
            from src.database import are_applications_accepted

            if are_applications_accepted():
                self.start_application(False)

    @classmethod
    def has_state_by_name(cls, name: str):
        return hasattr(cls, name) and type(getattr(cls, name)) == State

    @staticmethod
    def state_index(state: State):
        return [
            ApplicationState.waiting_for_applications,
            ApplicationState.filling_info,
            ApplicationState.filling_docs,
            ApplicationState.waiting_confirmation,
            ApplicationState.approved,
            ApplicationState.passed,
            ApplicationState.graduated,
        ].index(state)

    start_application = waiting_for_applications.to(filling_info)

    fill_info = filling_info.to(filling_docs) | filling_docs.to(filling_docs)

    fill_docs = filling_docs.to(waiting_confirmation)
    change_info = approved.to(filling_info) | waiting_confirmation.to(filling_info)
    program_cancelled = (
        filling_docs.to(filling_info)
        | waiting_confirmation.to(filling_info)
        | approved.to(filling_info)
        | not_passed.to(filling_info)
        | passed.to(filling_info)
    )

    approve = waiting_confirmation.to(approved)
    data_invalid = waiting_confirmation.to(filling_docs)

    not_pass = approved.to(not_passed)
    pass_ = approved.to(passed)
    graduate = passed.to(graduated)
    not_graduate = passed.to(not_passed)

    def get_user(self):
        from src.database import find_user

        return find_user(self.user_id).unwrap()

    def before_start_application(self, notify: bool):
        if notify:
            user = self.get_user()

            if user.application.notifyOnStart:
                mail.notify_on_application_start(
                    receiver=user.email,
                    full_name=user.fullName,
                )
                mail.notify_on_application_start(
                    receiver=user.parentEmail,
                    full_name=user.parentFullName,
                )

    def on_enter_filling_info(self):
        print(self.current_state.name)

    def on_enter_filling_docs(self):
        print(self.current_state.name)

    def on_enter_waiting_confirmation(self):
        print(self.current_state.name)

    def on_enter_approved(self):
        user = self.get_user()

        mail.notify_of_approval(
            receiver=user.email,
            full_name=user.fullName,
        )
        mail.notify_of_approval(
            receiver=user.parentEmail,
            full_name=user.parentFullName,
        )

        print(self.current_state.name)

    def on_enter_not_passed(self):
        # Отправить письмо
        print(self.current_state.name)

    def on_enter_passed(self):
        print(self.current_state.name)

    def on_enter_graduated(self):
        print(self.current_state.name)

    def before_data_invalid(self):
        # Отправить письмо

        user = self.get_user()

        mail.notify_of_approval(
            receiver=user.email,
            full_name=user.fullName,
            approved=False,
            rejection_reason=user.application.lastRejectionReason,
        )
        mail.notify_of_approval(
            receiver=user.parentEmail,
            full_name=user.fullName,
            approved=False,
            rejection_reason=user.application.lastRejectionReason,
        )


# model = MongodbPersistentModel(
#     UserKey(fullName="Иванов Иван Иванович", birthDate="12.04.2003")
# )

# state = ApplicationState(model=model)
# img_path = "cs_statemachine.png"

# state._graph().write_png(img_path)

# state.fill_info()
# state.fill_docs()
# state.docs_invalid("test2")
# state.fill_docs()
# state.approve()
# state.pass_()
# state.graduate()
