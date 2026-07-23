import logging
import sqlite3
import time
import datetime

from opcua import Client

import config
from opc_tags import TAGS

logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

logging.getLogger("opcua").setLevel(logging.WARNING)


def init_db():
    conn = sqlite3.connect(config.DB_FILE)
    cursor = conn.cursor()
    columns = ", ".join(f'"{name}" REAL' for name in TAGS)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            {columns}
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp)")
    conn.commit()
    conn.close()


def log_to_db(values: dict):
    conn = sqlite3.connect(config.DB_FILE)
    cursor = conn.cursor()
    columns = ", ".join(f'"{name}"' for name in values)
    placeholders = ", ".join("?" for _ in values)
    cursor.execute(
        f'INSERT INTO history (timestamp, {columns}) VALUES (?, {placeholders})',
        [datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")] + list(values.values()),
    )
    conn.commit()
    conn.close()


def purge_old_records():
    cutoff = (datetime.datetime.now() - datetime.timedelta(hours=config.HISTORY_RETENTION_HOURS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn = sqlite3.connect(config.DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE timestamp < ?", (cutoff,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    if deleted:
        logger.info("Удалено %d устаревших записей истории", deleted)


def format_summary(values: dict) -> str:
    """Компактная однострочная сводка вместо сырого словаря — удобнее читать в терминале."""
    mode = "AUTO" if values.get("ControlMode", 0) >= 0.5 else "MANUAL"
    alarm = " ⚠ АВАРИЯ" if values.get("Overflow", 0) >= 0.5 else ""
    return (
        f"[{mode}] "
        f"Уровень={values['WaterLevel']:5.1f}%  "
        f"Т.вых={values['OutputTemp']:5.1f}°C  "
        f"Клапаны: Г={values['ValveHotIn']*100:3.0f}% Х={values['ValveColdIn']*100:3.0f}% Вых={values['ValveOut']*100:3.0f}%"
        f"{alarm}"
    )


def main():
    init_db()
    client = Client(config.OPC_ENDPOINT)
    try:
        client.connect()
        logger.info(" Исторический логгер подключён к OPC UA (%s)", config.OPC_ENDPOINT)
        logger.info("Записи сохраняются в %s каждые %.0f сек", config.DB_FILE, config.HISTORY_LOG_INTERVAL_SECONDS)
        boiler = client.get_root_node().get_child(["0:Objects", "2:Boiler"])
        nodes = {name: boiler.get_child(f"2:{name}") for name in TAGS}

        tick = 0
        while True:
            values = {name: node.get_value() for name, node in nodes.items()}
            log_to_db(values)
            logger.info(format_summary(values))

            tick += 1
            if tick % 100 == 0:
                purge_old_records()

            time.sleep(config.HISTORY_LOG_INTERVAL_SECONDS)
    except Exception as e:
        logger.error("Ошибка логгера: %s", e)
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()