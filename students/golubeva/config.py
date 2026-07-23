import os
from dotenv import load_dotenv

load_dotenv()

OPC_ENDPOINT = os.getenv("OPC_ENDPOINT", "opc.tcp://0.0.0.0:4840/freeopcua/server/")
OPC_NAMESPACE_URI = os.getenv("OPC_NAMESPACE_URI", "http://example.org/boiler/")

FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5001))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"

MODEL_STEP_SECONDS = float(os.getenv("MODEL_STEP_SECONDS", 0.1))
HISTORY_LOG_INTERVAL_SECONDS = float(os.getenv("HISTORY_LOG_INTERVAL_SECONDS", 5.0))

DB_FILE = os.getenv("DB_FILE", "data.db")
HISTORY_RETENTION_HOURS = int(os.getenv("HISTORY_RETENTION_HOURS", 24))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")