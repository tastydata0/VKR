import statemachine  # type: ignore
from src.models import ApplicationStage
from src.application_state import ApplicationState


def status(current_state, state):
    if ApplicationState.state_index(current_state) == ApplicationState.state_index(
        state
    ):
        return "current"
    elif ApplicationState.state_index(current_state) > ApplicationState.state_index(
        state
    ):
        return "passed"
    else:
        return "todo"


def get_stages_according_to_state(state: statemachine.State):
    return [
        ApplicationStage(
            stageName="Ожидание начала сбора заявлений",
            stageStatus=status(state, ApplicationState.waiting_for_applications),
            stageHref="#",
        ),
        ApplicationStage(
            stageName="Ввод данных и выбор программы",
            stageStatus=status(state, ApplicationState.filling_info),
            stageHref="/application/fill_info",
        ),
        ApplicationStage(
            stageName="Загрузка документов",
            stageStatus=status(state, ApplicationState.filling_docs),
            stageHref="/application/fill_docs",
        ),
        ApplicationStage(
            stageName="Ожидание подтверждения",
            stageStatus=status(state, ApplicationState.waiting_confirmation),
            stageHref="/application/waiting_confirmation",
        ),
        ApplicationStage(
            stageName="Заявление принято",
            stageStatus=status(state, ApplicationState.approved),
            stageHref="/application/approved",
        ),
        # ApplicationStage(
        #     stageName="Не прошел конкурс на программу", stageStatus="negative"
        # ),
        ApplicationStage(
            stageName="Зачислен на программу",
            stageStatus=status(state, ApplicationState.passed),
            stageHref="/application/passed",
        ),
        ApplicationStage(
            stageName="Программа пройдена", stageStatus="todo", stageHref="#"
        ),
    ]
