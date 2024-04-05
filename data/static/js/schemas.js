add_program_schema = {
    type: "object",
    title: "Добавить программу",
    properties: {
        baseId: {
            type: "string",
            title: "ID",
            description: "Это поле нельзя будет изменить позже",
        },
        brief: {
            type: "string",
            title: "Краткое название"
        },
        infoHtml: {
            title: "Описание на HTML",
            type: "string",
            format: "textarea"
        },
        difficulty: {
            title: "Сложность",
            type: "integer",
            enum: [0, 1, 2, 3]
        },
        iconUrl: {
            title: "URL иконки",
            type: "string",
            format: "url"
        }
    }
}