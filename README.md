# Производственная практика 2026 — OPC UA проект

## Описание
Учебный проект: каждый участник самостоятельно реализует 
симулятор бойлера с OPC UA сервером.

## Участники
| Папка | Студент |
|-------|---------|
| students/golubeva/ | Голубева |
| students/mamaev/ | Мамаев |
| students/rikhelgof/ | Рихельгоф |
| students/khabarov/ | Хабаров |

## Структура папки каждого студента
```
students/<имя>/
├── src/
│   ├── boiler_model.py
│   ├── opc_server.py
│   ├── server_main.py
│   ├── opcua_client.py
│   └── history_logger.py
├── requirements.txt
├── Dockerfile
└── README.md
```

## Как работать
1. Клонируй репозиторий
2. Создай ветку: `git checkout -b feature/<твоя-фамилия>`
3. Пиши код только в своей папке `students/<твоя-фамилия>/`
4. Создай Pull Request в main когда готово
5. CI проверит твой код автоматически

## Задание
Подробное описание задания в [docs/task.md](docs/task.md)