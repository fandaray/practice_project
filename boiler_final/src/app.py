"""
Веб-панель SCADA для бойлера. Решение rikhelgof (студент), адаптировано
под общий модуль opcua_client.py (вместо собственного клиента внутри app.py).

Flask-приложение выступает OPC UA клиентом: читает измерения и алармы,
принимает от браузера команды на изменение уставок клапанов/нагревателя/
авторегуляторов и пишет их обратно в адресное пространство сервера.
При обрыве связи с OPC UA сервером клиент пересоздаётся на следующий запрос
(автопереподключение), чтобы панель сама восстанавливалась после перезапуска
сервера.

Запуск:  python app.py
Панель:  http://localhost:5050
"""

import logging
import threading

from flask import Flask, jsonify, request, render_template

import config
from opcua_client import BoilerOpcUaClient, WRITABLE_TAGS, validate_value

logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("opcua").setLevel(logging.WARNING)
log = logging.getLogger("boiler-scada-dashboard")

app = Flask(__name__)

_client_lock = threading.Lock()
_client: BoilerOpcUaClient | None = None


def get_client() -> BoilerOpcUaClient:
    """Ленивое подключение к OPC UA серверу с автопереподключением (rikhelgof)."""
    global _client
    with _client_lock:
        if _client is not None:
            return _client
        client = BoilerOpcUaClient()
        client.connect()
        _client = client
        return _client


def reset_client():
    global _client
    with _client_lock:
        if _client is not None:
            _client.disconnect()
        _client = None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    try:
        client = get_client()
        state = client.get_all_values()
        state["connected"] = True
        return jsonify(state)
    except Exception as exc:
        log.warning("Не удалось прочитать состояние: %s", exc)
        reset_client()
        return jsonify({"connected": False, "error": str(exc)}), 503


@app.route("/api/setpoint", methods=["POST"])
def api_setpoint():
    payload = request.get_json(force=True, silent=True) or {}
    tag = payload.get("tag")
    value = payload.get("value")

    if tag not in WRITABLE_TAGS:
        return jsonify({"ok": False, "error": f"тег '{tag}' недоступен для записи"}), 400

    try:
        value = validate_value(tag, value)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "некорректное значение"}), 400

    try:
        client = get_client()
        client.set_value(tag, value)
        return jsonify({"ok": True, "tag": tag, "value": value})
    except Exception as exc:
        log.warning("Не удалось записать уставку %s=%s: %s", tag, value, exc)
        reset_client()
        return jsonify({"ok": False, "error": str(exc)}), 503


if __name__ == "__main__":
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)
