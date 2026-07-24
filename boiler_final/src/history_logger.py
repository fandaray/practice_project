"""
Отдельный процесс (согласно заданию): каждые config.HISTORY_LOG_INTERVAL_SECONDS
секунд (по умолчанию 5) читает данные с OPC UA сервера и пишет срез в SQLite.

Схема таблицы и общий подход - решение rikhelgof (студент), переиспользует
общий BoilerOpcUaClient. Автоматическая очистка устаревших записей
(retention) - решение golubeva (студент).

Запуск:  python history_logger.py
"""

import logging
import sqlite3
import time
import datetime
from pathlib import Path

import config
from opcua_client import BoilerOpcUaClient

logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logging.getLogger("opcua").setLevel(logging.WARNING)
log = logging.getLogger("boiler-history-logger")

# какие теги пишем в историю (срез, не всё адресное пространство целиком)
LOGGED_TAGS = [
    "level", "temperature", "temperature_valid", "pressure",
    "hot_valve", "cold_valve", "outlet_valve", "heater",
    "hot_valve_effective", "cold_valve_effective", "heater_effective",
    "level_auto", "temperature_auto",
    "level_high_alarm", "level_low_alarm", "overtemp_alarm",
    "interlock_overflow", "interlock_overtemp",
]


def ensure_schema(conn: sqlite3.Connection):
    columns = ", ".join(f'"{name}" REAL' for name in LOGGED_TAGS)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS boiler_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            {columns}
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_boiler_history_ts ON boiler_history(timestamp)")
    conn.commit()


def store(conn: sqlite3.Connection, values: dict):
    row = {name: values[name] for name in LOGGED_TAGS}
    columns = ", ".join(f'"{name}"' for name in row)
    placeholders = ", ".join(f":{name}" for name in row)
    row["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        f'INSERT INTO boiler_history (timestamp, {columns}) VALUES (:timestamp, {placeholders})',
        row,
    )
    conn.commit()


def purge_old_records(conn: sqlite3.Connection):
    """Удаляет записи старше config.HISTORY_RETENTION_HOURS часов (golubeva)."""
    cutoff = (
        datetime.datetime.now() - datetime.timedelta(hours=config.HISTORY_RETENTION_HOURS)
    ).strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.execute("DELETE FROM boiler_history WHERE timestamp < ?", (cutoff,))
    conn.commit()
    if cursor.rowcount:
        log.info("Удалено %d устаревших записей истории (старше %d ч)", cursor.rowcount, config.HISTORY_RETENTION_HOURS)


def format_summary(values: dict) -> str:
    mode = []
    if values.get("level_auto"):
        mode.append("LEVEL-AUTO")
    if values.get("temperature_auto"):
        mode.append("TEMP-AUTO")
    mode_str = "+".join(mode) if mode else "MANUAL"
    alarm = " ⚠" if values.get("interlock_overflow") or values.get("interlock_overtemp") else ""
    return (
        f"[{mode_str}] "
        f"Уровень={values['level']:5.1f}%  Т={values['temperature']:5.1f}°C  "
        f"Давл={values['pressure']:.2f}бар  "
        f"Г={values['hot_valve_effective']:3.0f}% Х={values['cold_valve_effective']:3.0f}% "
        f"Вых={values['outlet_valve']:3.0f}%"
        f"{alarm}"
    )


def main():
    Path(config.DB_FILE).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_FILE)
    ensure_schema(conn)

    client = BoilerOpcUaClient()
    try:
        client.connect()
        log.info("Логгер истории подключён к %s", client.endpoint)
        log.info("Пишу в %s каждые %.0f сек, хранение %d ч", config.DB_FILE,
                  config.HISTORY_LOG_INTERVAL_SECONDS, config.HISTORY_RETENTION_HOURS)

        tick = 0
        while True:
            values = client.get_all_values()
            store(conn, values)
            log.info(format_summary(values))

            tick += 1
            if tick % 100 == 0:
                purge_old_records(conn)

            time.sleep(config.HISTORY_LOG_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        log.info("Остановка по Ctrl+C")
    except Exception as e:
        log.error("Ошибка логгера: %s", e)
    finally:
        client.disconnect()
        conn.close()


if __name__ == "__main__":
    main()
