"""
Веб-панель SCADA для бойлера.

Flask-приложение выступает OPC UA клиентом: читает измерения и алармы,
принимает от браузера команды на изменение уставок клапанов/нагревателя
и пишет их обратно в адресное пространство сервера.

Запуск:  python -m scada_dashboard.app
Панель:  http://localhost:5050
"""

import logging
import threading
from typing import Optional

from flask import Flask, jsonify, request, render_template
from opcua import Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("boiler-scada-dashboard")

SERVER_URL = "opc.tcp://localhost:4841/boiler/server/"
NAMESPACE_URI = "http://example.org/boiler-scada"

# пути заданы БЕЗ индекса пространства имён - реальный индекс сервер выдаёт
# динамически при регистрации namespace и может отличаться от запуска к запуску
TAG_PATHS = {
    "level": ["Boiler", "Measurements", "Level"],
    "temperature": ["Boiler", "Measurements", "Temperature"],
    "temperature_valid": ["Boiler", "Measurements", "TemperatureValid"],
    "pressure": ["Boiler", "Measurements", "Pressure"],
    "hot_valve": ["Boiler", "Setpoints", "HotValve"],
    "cold_valve": ["Boiler", "Setpoints", "ColdValve"],
    "outlet_valve": ["Boiler", "Setpoints", "OutletValve"],
    "heater": ["Boiler", "Setpoints", "Heater"],
    "level_setpoint": ["Boiler", "Setpoints", "LevelSetpoint"],
    "level_auto": ["Boiler", "Setpoints", "LevelAuto"],
    "temperature_setpoint": ["Boiler", "Setpoints", "TemperatureSetpoint"],
    "temperature_auto": ["Boiler", "Setpoints", "TemperatureAuto"],
    "level_high_alarm": ["Boiler", "Alarms", "LevelHigh"],
    "level_low_alarm": ["Boiler", "Alarms", "LevelLow"],
    "overtemp_alarm": ["Boiler", "Alarms", "OverTemperature"],
    "interlock_overflow": ["Boiler", "Interlocks", "Overflow"],
    "interlock_overtemp": ["Boiler", "Interlocks", "Overtemp"],
    "hot_valve_effective": ["Boiler", "Effective", "HotValve"],
    "cold_valve_effective": ["Boiler", "Effective", "ColdValve"],
    "heater_effective": ["Boiler", "Effective", "Heater"],
}

# тип каждого доступного для записи тега определяет, как валидировать значение
WRITABLE_TAGS = {
    "hot_valve": "percent",
    "cold_valve": "percent",
    "outlet_valve": "percent",
    "heater": "percent",
    "level_setpoint": "percent",
    "level_auto": "bool",
    "temperature_setpoint": "temperature",
    "temperature_auto": "bool",
}

app = Flask(__name__)

_client_lock = threading.Lock()
_client: Optional[Client] = None
_nodes: dict = {}


def get_client() -> Client:
    """Ленивое подключение к OPC UA серверу с автопереподключением."""
    global _client, _nodes
    with _client_lock:
        if _client is not None:
            return _client
        client = Client(SERVER_URL)
        client.connect()
        ns = client.get_namespace_index(NAMESPACE_URI)
        objects = client.get_objects_node()
        _nodes = {
            name: objects.get_child([f"{ns}:{part}" for part in path])
            for name, path in TAG_PATHS.items()
        }
        _client = client
        log.info("Подключились к OPC UA серверу %s", SERVER_URL)
        return _client


def reset_client():
    global _client
    with _client_lock:
        if _client is not None:
            try:
                _client.disconnect()
            except Exception:
                pass
        _client = None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    try:
        get_client()
        state = {name: node.get_value() for name, node in _nodes.items()}
        state["connected"] = True
        return jsonify(state)
    except Exception as exc:  # сервер недоступен / оборвалось соединение
        log.warning("Не удалось прочитать состояние: %s", exc)
        reset_client()
        return jsonify({"connected": False, "error": str(exc)}), 503


@app.route("/api/setpoint", methods=["POST"])
def api_setpoint():
    payload = request.get_json(force=True, silent=True) or {}
    tag = payload.get("tag")
    value = payload.get("value")

    tag_type = WRITABLE_TAGS.get(tag)
    if tag_type is None:
        return jsonify({"ok": False, "error": f"тег '{tag}' недоступен для записи"}), 400

    if tag_type == "bool":
        value = bool(value)
    else:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "value должен быть числом"}), 400
        if tag_type == "percent":
            value = max(0.0, min(100.0, value))
        elif tag_type == "temperature":
            value = max(10.0, min(95.0, value))  # верхний предел = порог блокировки перегрева

    try:
        get_client()
        _nodes[tag].set_value(value)
        return jsonify({"ok": True, "tag": tag, "value": value})
    except Exception as exc:
        log.warning("Не удалось записать уставку %s=%s: %s", tag, value, exc)
        reset_client()
        return jsonify({"ok": False, "error": str(exc)}), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
