"""
Конфигурация проекта через переменные окружения. Паттерн - решение
golubeva (студент): значения по умолчанию совпадают с требованиями
задания, но их можно переопределить через .env или переменные окружения
Docker-контейнера, не трогая код.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "boiler_history.sqlite3"

OPC_ENDPOINT = os.getenv("OPC_ENDPOINT", "opc.tcp://0.0.0.0:4840/boiler/server/")
OPC_ENDPOINT_CLIENT = os.getenv("OPC_ENDPOINT_CLIENT", "opc.tcp://localhost:4840/boiler/server/")
OPC_NAMESPACE_URI = os.getenv("OPC_NAMESPACE_URI", "http://example.org/boiler-scada")

FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5050))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

MODEL_STEP_SECONDS = float(os.getenv("MODEL_STEP_SECONDS", 1.0))
HISTORY_LOG_INTERVAL_SECONDS = float(os.getenv("HISTORY_LOG_INTERVAL_SECONDS", 5.0))

DB_FILE = os.getenv("DB_FILE", str(_DEFAULT_DB_PATH))
HISTORY_RETENTION_HOURS = int(os.getenv("HISTORY_RETENTION_HOURS", 24))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
