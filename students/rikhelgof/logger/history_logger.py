"""
Клиент OPC UA, который периодически опрашивает сервер бойлера
и пишет срез параметров в SQLite (историческая таблица тренда).

Запуск:  python -m logger.history_logger
"""

import time
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

from opcua import Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("boiler-history-logger")

SERVER_URL = "opc.tcp://localhost:4841/boiler/server/"
NAMESPACE_URI = "http://example.org/boiler-scada"
POLL_PERIOD_S = 5.0
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "boiler_history.sqlite3"

# пути заданы БЕЗ индекса пространства имён - реальный индекс сервер выдаёт
# динамически при регистрации namespace и может отличаться от запуска к запуску
TAGS = {
    "level": ["Boiler", "Measurements", "Level"],
    "temperature": ["Boiler", "Measurements", "Temperature"],
    "temperature_valid": ["Boiler", "Measurements", "TemperatureValid"],
    "pressure": ["Boiler", "Measurements", "Pressure"],
    "hot_valve": ["Boiler", "Setpoints", "HotValve"],
    "cold_valve": ["Boiler", "Setpoints", "ColdValve"],
    "outlet_valve": ["Boiler", "Setpoints", "OutletValve"],
    "level_auto": ["Boiler", "Setpoints", "LevelAuto"],
    "temperature_auto": ["Boiler", "Setpoints", "TemperatureAuto"],
    "level_high_alarm": ["Boiler", "Alarms", "LevelHigh"],
    "level_low_alarm": ["Boiler", "Alarms", "LevelLow"],
    "overtemp_alarm": ["Boiler", "Alarms", "OverTemperature"],
    "interlock_overflow": ["Boiler", "Interlocks", "Overflow"],
    "interlock_overtemp": ["Boiler", "Interlocks", "Overtemp"],
}


def ensure_schema(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS boiler_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            level REAL,
            temperature REAL,
            temperature_valid INTEGER,
            pressure REAL,
            hot_valve REAL,
            cold_valve REAL,
            outlet_valve REAL,
            level_auto INTEGER,
            temperature_auto INTEGER,
            level_high_alarm INTEGER,
            level_low_alarm INTEGER,
            overtemp_alarm INTEGER,
            interlock_overflow INTEGER,
            interlock_overtemp INTEGER
        )
        """
    )
    conn.commit()


def resolve_nodes(client: Client):
    ns = client.get_namespace_index(NAMESPACE_URI)
    objects = client.get_objects_node()
    return {
        name: objects.get_child([f"{ns}:{part}" for part in path])
        for name, path in TAGS.items()
    }


def poll_once(nodes: dict) -> dict:
    values = {name: node.get_value() for name, node in nodes.items()}
    values["ts"] = datetime.now(timezone.utc).isoformat()
    return values


def store(conn: sqlite3.Connection, row: dict):
    conn.execute(
        """
        INSERT INTO boiler_history
            (ts, level, temperature, temperature_valid, pressure, hot_valve, cold_valve, outlet_valve,
             level_auto, temperature_auto,
             level_high_alarm, level_low_alarm, overtemp_alarm,
             interlock_overflow, interlock_overtemp)
        VALUES (:ts, :level, :temperature, :temperature_valid, :pressure, :hot_valve, :cold_valve, :outlet_valve,
                :level_auto, :temperature_auto,
                :level_high_alarm, :level_low_alarm, :overtemp_alarm,
                :interlock_overflow, :interlock_overtemp)
        """,
        row,
    )
    conn.commit()


def run():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    client = Client(SERVER_URL)
    client.connect()
    log.info("Подключились к %s", SERVER_URL)
    nodes = resolve_nodes(client)

    try:
        while True:
            row = poll_once(nodes)
            store(conn, row)
            log.info(
                "level=%.1f%% temp=%.1f°C pressure=%.2f bar",
                row["level"], row["temperature"], row["pressure"],
            )
            time.sleep(POLL_PERIOD_S)
    except KeyboardInterrupt:
        log.info("Остановка по Ctrl+C")
    finally:
        client.disconnect()
        conn.close()


if __name__ == "__main__":
    run()
