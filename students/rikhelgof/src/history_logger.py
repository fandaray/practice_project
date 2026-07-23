"""
Периодически опрашивает сервер бойлера через opcua_client
и пишет срез параметров в SQLite (историческая таблица тренда).

Запуск:  python history_logger.py
"""

import time
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

from opcua_client import connect, resolve_nodes, poll_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("boiler-history-logger")

POLL_PERIOD_S = 5.0
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "boiler_history.sqlite3"


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

    client = connect()
    nodes = resolve_nodes(client)

    try:
        while True:
            row = poll_values(nodes)
            row["ts"] = datetime.now(timezone.utc).isoformat()
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
