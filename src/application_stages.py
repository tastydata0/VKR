from models import ApplicationStage

application_stages = [
    ApplicationStage(stageName="Ожидание начала сбора заявлений", stageStatus="passed"),
    ApplicationStage(
        stageName="Ввод данных и выбор программы", stageStatus="passed", stageHref="/"
    ),
    ApplicationStage(
        stageName="Загрузка документов", stageStatus="todo", stageHref="/send_docs"
    ),
    ApplicationStage(stageName="Ожидание подтверждения", stageStatus="todo"),
    ApplicationStage(stageName="Заявление принято", stageStatus="todo"),
    ApplicationStage(
        stageName="Не прошел конкурс на программу", stageStatus="negative"
    ),
    ApplicationStage(stageName="Зачислен на программу", stageStatus="todo"),
    ApplicationStage(stageName="Программа пройдена", stageStatus="todo"),
]
