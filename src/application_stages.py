from models import ApplicationStage

application_stages = [
    ApplicationStage(stageName="Ожидание начала сбора заявлений", stageStatus="passed"),
    ApplicationStage(
        stageName="Ввод данных и выбор программы",
        stageStatus="passed",
        stageHref="/application/fill_info",
    ),
    ApplicationStage(
        stageName="Загрузка документов",
        stageStatus="todo",
        stageHref="/application/fill_docs",
    ),
    ApplicationStage(
        stageName="Ожидание подтверждения",
        stageStatus="todo",
        stageHref="/application/waiting_confirmation",
    ),
    ApplicationStage(
        stageName="Заявление принято",
        stageStatus="todo",
        stageHref="/application/approved",
    ),
    ApplicationStage(
        stageName="Не прошел конкурс на программу", stageStatus="negative"
    ),
    ApplicationStage(
        stageName="Зачислен на программу",
        stageStatus="todo",
        stageHref="/application/passed",
    ),
    ApplicationStage(stageName="Программа пройдена", stageStatus="todo"),
]
