# Производственная практика 2026 — OPC UA проект

## Описание
Учебный репозиторий. Каждый участник самостоятельно реализует
полную систему симуляции бойлера с OPC UA сервером.

## Участники
| Папка | Студент | GitHub |
|-------|---------|--------|
| students/golubeva/ | Голубева | @golubeva-username |
| students/mamaev/ | Мамаев | @han-128 |
| students/rikhelgof/ | Рикхельгоф | @Surevio |
| students/khabarov/ | Хабаров | @artemka1175 |

## Структура папки каждого студента
'''
students/<имя>/
├── src/
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/main.js
│   ├── templates/
│   │   └── index.html
│   ├── app.py
│   ├── boiler_model.py
│   ├── history_logger.py
│   ├── opcua_client.py
│   ├── opc_server.py
│   ├── opc_tags.py
│   ├── run_model.py
│   ├── run_server.py
│   ├── server_main.py
│   └── viewer.py
├── Dockerfile
├── requirements.txt
└── README.md
'''
## Как работать

### 1. Клонировать репозиторий
```bash
git clone https://github.com/fandaray/practice_project.git
cd practice_project
```

### 2. Создать свою ветку
```bash
git checkout -b feature/<твоя-фамилия>
```

### 3. Писать код только в своей папке
```bash
students/<твоя-фамилия>/src/
```

### 4. Закоммитить и запушить
```bash
git add students/<твоя-фамилия>/
git commit -m "Описание что сделал"
git push origin feature/<твоя-фамилия>
```

### 5. Создать Pull Request
На GitHub появится кнопка **Compare & pull request** — нажать и создать PR в main.

## Запуск всех проектов сразу
```bash
docker compose up
```
Каждый проект поднимается на своём порту:
| Студент | Порт |
|---------|------|
| Голубева | 4841 |
| Мамаев | 4842 |
| Рикхельгоф | 4843 |
| Хабаров | 4844 |

## Задание
Подробное описание в [docs/task.md](docs/task.md)

## Пример для изучения
https://github.com/madvln/opcua_practice