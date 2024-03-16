from dataclasses import dataclass
from statemachine import StateMachine, State
from models import UserKey

from persistent_model import MongodbPersistentModel

IS_APPLICATIONS_STARTED = True


class ApplicationState(StateMachine):
    waiting_for_applications = State("Ожидание начала сбора заявлений", initial=True)
    filling_info = State("Ввод данных и выбор программы")
    filling_docs = State("Загрузка документов")
    waiting_confirmation = State("Ожидание подтверждения")
    approved = State("Заявление принято")
    not_passed = State("Не прошел конкурс на программу", final=True)
    passed = State("Зачислен на программу")
    graduated = State("Программа пройдена", final=True)

    start_application = waiting_for_applications.to(filling_info)

    fill_info = filling_info.to(filling_docs) | filling_docs.to(filling_docs)

    fill_docs = filling_docs.to(waiting_confirmation)
    change_info = filling_docs.to(filling_info) | waiting_confirmation.to(filling_info)
    program_cancelled = filling_docs.to(filling_info) | waiting_confirmation.to(
        filling_info
    )

    approve = waiting_confirmation.to(approved)
    docs_invalid = waiting_confirmation.to(filling_docs)

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

    def on_enter_approved(self):
        print(self.current_state.name)

    def on_enter_not_passed(self):
        print(self.current_state.name)

    def on_enter_passed(self):
        print(self.current_state.name)

    def on_enter_graduated(self):
        print(self.current_state.name)

    def before_docs_invalid(self, message: str = ""):
        print("Docs invalid:", message)


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
