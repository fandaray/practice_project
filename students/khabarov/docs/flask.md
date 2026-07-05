
# Flask - полное руководство

## Что такое Flask?

**Flask** — это **микрофреймворк** для создания веб-приложений на языке Python. Он лёгкий, гибкий и минималистичный, что позволяет разработчику самому выбирать, какие инструменты использовать (БД, ORM, аутентификацию и т.д.).

Flask создан в 2010 году **Armin Ronacher** и основан на библиотеках **Werkzeug** (WSGI) и **Jinja2** (шаблонизатор).


---

## Основные особенности Flask

- **Минималистичный** — только ядро (routing, request/response, templating)
- **Расширяемый** — огромное количество расширений (Flask-SQLAlchemy, Flask-Login, Flask-RESTful и др.)
- **Werkzeug** — мощный WSGI-сервер для разработки
- **Jinja2** — безопасный и мощный шаблонизатор
- **RESTful** — легко создавать API
- **Поддержка Blueprints** — для модульной архитектуры

---

## Виды / Подходы к использованию Flask

| Тип проекта               | Рекомендуемый подход                     | Расширения                              |
|---------------------------|------------------------------------------|-----------------------------------------|
| Простое API               | Flask + Flask-RESTful / Flask-RESTX      | flask-cors                              |
| Полноценное веб-приложение| Flask + Blueprints + Jinja2              | Flask-SQLAlchemy, Flask-WTF             |
| Большой проект            | Application Factory + Blueprints         | Flask-Migrate, Flask-Login, Celery      |
| Микросервис               | Flask + Docker + Gunicorn                | Flask-JWT-Extended                      |
| IoT / SCADA Web-панель    | Flask + OPC UA + WebSocket               | flask-socketio                          |

---

## Сравнение Flask и Django

| Критерий                    | Flask                              | Django                              |
|----------------------------|------------------------------------|-------------------------------------|
| Философия                  | Микрофреймворк ("батарейки отдельно") | "Всё включено" (Batteries Included)|
| Скорость обучения          | Быстрее                            | Медленнее (больше возможностей)     |
| Гибкость                   | Очень высокая                      | Средняя (строгая структура)         |
| Размер проекта             | От маленьких до крупных            | Лучше для крупных проектов          |
| ORM                        | Нет (Flask-SQLAlchemy)             | Встроенный (Django ORM)             |
| Админ-панель               | Нет (Flask-Admin)                  | Встроенная                          |
| REST API                   | Нужно использовать расширения      | Django REST Framework               |
| Производительность         | Выше                               | Чуть ниже                           |
| Сообщество / расширения    | Отличное                           | Очень большое                       |

**Когда выбирать Flask:**
- Нужно максимальную гибкость
- Создаёте API / микросервис
- Интегрируете с OPC UA, MQTT, Socket.IO и т.д.
- Небольшая или средняя команда

---

## Плюсы Flask

1. **Лёгкость и минимализм**
2. **Высокая производительность**
3. **Отличная гибкость**
4. **Простота тестирования**
5. **Большая экосистема расширений**
6. **Легко интегрируется** с другими технологиями (OPC UA, databases, Redis и т.д.)
7. **Хорошо подходит для обучения**

---

## Минусы Flask

1. **Нет "из коробки"** — нужно самостоятельно подключать всё необходимое
2. **Структура проекта** — разработчик сам решает (может привести к хаосу в больших проектах)
3. **Отсутствие встроенной админки**
4. **Безопасность** — нужно вручную настраивать (CSRF, JWT, rate limiting)
5. **Масштабирование** — требует дополнительных инструментов (Gunicorn, Nginx, Celery)

---

## Примеры кода

### 1. Базовое приложение (app.py)

```python
# app.py
from flask import Flask, render_template, jsonify, request
import json

app = Flask(__name__)

# Конфигурация
app.config['SECRET_KEY'] = 'your-secret-key-here'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/boiler/status')
def boiler_status():
    """Пример API для модели бойлера"""
    status = {
        "level": 45.5,
        "temperature": 67.3,
        "hot_valve": 0.6,
        "cold_valve": 0.4,
        "out_valve": 1.0,
        "timestamp": "2026-07-05T12:15:00"
    }
    return jsonify(status)

@app.route('/api/boiler/valve', methods=['POST'])
def set_valve():
    """Изменение положения клапана"""
    data = request.get_json()
    valve = data.get('valve')
    value = data.get('value')
    
    # Здесь логика отправки команды в OPC UA сервер
    return jsonify({
        "status": "success",
        "valve": valve,
        "value": value
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)

### 2. Application Factory

```python
# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    
    db.init_app(app)
    
    # Регистрация Blueprint'ов
    from .main import main_bp
    from .api import api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app

3. Пример интеграции с OPC UA
```python
# app/api/opc.py
from flask import Blueprint, jsonify
from opcua import Client

opc_bp = Blueprint('opc', __name__)

@opc_bp.route('/opc/status')
def get_opc_status():
    try:
        client = Client("opc.tcp://localhost:4840/freeopcua/server/")
        client.connect()
        
        root = client.get_objects_node()
        boiler = root.get_child(["2:Boiler"])
        
        data = {
            "level": boiler.get_child(["2:Level"]).get_value(),
            "temperature": boiler.get_child(["2:Temperature"]).get_value(),
        }
        client.disconnect()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

4. Шаблон Jinja2
```HTML

<!DOCTYPE html>
<html>
<head>
    <title>Мониторинг Бойлера</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <h1>Состояние бойлера</h1>
    <div id="status">
        <p>Уровень: <span id="level">{{ level }}%</span></p>
        <p>Температура: <span id="temp">{{ temperature }}°C</span></p>
    </div>
    
    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
</body>
</html>

## Полезные расширения Flask

- Flask-SQLAlchemy — работа с БД
- Flask-Migrate — миграции
- Flask-Login — аутентификация
- Flask-JWT-Extended — JWT токены
- Flask-SocketIO — WebSocket
- Flask-Admin — административная панель
- Flask-CORS — для API