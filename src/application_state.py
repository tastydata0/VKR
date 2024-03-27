from dataclasses import dataclass
from statemachine import StateMachine, State
from mail_service import Mail

IS_APPLICATIONS_STARTED = True


class ApplicationState(StateMachine):
    waiting_for_applications = State("Ожидание начала сбора заявлений", initial=True)
    filling_info = State("Ввод данных и выбор программы")
    filling_docs = State("Загрузка документов")
    waiting_confirmation = State("Ожидание подтверждения")
    approved = State("Заявление принято")
    not_passed = State("Не прошел конкурс на программу")
    passed = State("Зачислен на программу")
    graduated = State("Программа пройдена", final=True)

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

    def on_enter_waiting_for_applications(self):
        print(self.current_state.name)
        if IS_APPLICATIONS_STARTED:
            self.start_application()

    def on_enter_filling_info(self):
        print(self.current_state.name)

    def on_enter_filling_docs(self):
        print(self.current_state.name)

    def on_enter_waiting_confirmation(self):
        print(self.current_state.name)

    def on_enter_approved(self, user):
        # Отправить письмо
        mail = Mail()
        if user.email:
            mail.notify_of_approval(
                receiver=user.email,
                full_name=user.fullName,
                approved=False,
                rejection_reason=user.application.lastRejectionReason,
            )
        if user.parentEmail:
            mail.notify_of_approval(
                receiver=user.parentEmail,
                full_name=user.fullName,
                approved=False,
                rejection_reason=user.application.lastRejectionReason,
            )

        print(self.current_state.name)

    def on_enter_not_passed(self):
        # Отправить письмо
        print(self.current_state.name)

    def on_enter_passed(self):
        print(self.current_state.name)

    def on_enter_graduated(self):
        print(self.current_state.name)

    def before_data_invalid(self, user):
        # Отправить письмо

        mail = Mail()
        if user.email:
            mail.notify_of_approval(
                receiver=user.email,
                full_name=user.fullName,
                approved=False,
                rejection_reason=user.application.lastRejectionReason,
            )
        if user.parentEmail:
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
