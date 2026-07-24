"""
OPC UA клиент бойлера. По заданию: подключается к серверу и читает
текущие данные (уровень, температура, клапаны). Подход к разрешению
адресов - решение rikhelgof (студент): пути заданы БЕЗ индекса
пространства имён, реальный индекс сервер выдаёт динамически при
регистрации namespace и может отличаться от запуска к запуску, поэтому
индекс всегда узнаётся через get_namespace_index() и подставляется в
путь на лету, а не хардкодится в коде.

Используется как библиотека в app.py (веб-панель) и history_logger.py,
и может быть запущен отдельно для быстрой проверки связи с сервером.

Запуск:  python opcua_client.py
"""

import logging

from opcua import Client

import config

logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("opcua").setLevel(logging.WARNING)
log = logging.getLogger("boiler-opcua-client")

# пути в адресном пространстве без индекса namespace - см. пояснение выше
TAG_PATHS = {
    "level": ["Boiler", "Measurements", "Level"],
    "temperature": ["Boiler", "Measurements", "Temperature"],
    "temperature_valid": ["Boiler", "Measurements", "TemperatureValid"],
    "pressure": ["Boiler", "Measurements", "Pressure"],

    "hot_valve": ["Boiler", "Setpoints", "HotValve"],
    "cold_valve": ["Boiler", "Setpoints", "ColdValve"],
    "outlet_valve": ["Boiler", "Setpoints", "OutletValve"],
    "heater": ["Boiler", "Setpoints", "Heater"],
    "valve_travel_time": ["Boiler", "Setpoints", "ValveTravelTime"],
    "input_temp_hot": ["Boiler", "Setpoints", "InputTempHot"],
    "input_temp_cold": ["Boiler", "Setpoints", "InputTempCold"],
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

# теги, доступные для записи с клиента, и как валидировать присланное значение
WRITABLE_TAGS = {
    "hot_valve": "percent",
    "cold_valve": "percent",
    "outlet_valve": "percent",
    "heater": "percent",
    "valve_travel_time": "seconds",
    "input_temp_hot": "temperature_wide",
    "input_temp_cold": "temperature_wide",
    "level_setpoint": "percent",
    "level_auto": "bool",
    "temperature_setpoint": "temperature",
    "temperature_auto": "bool",
}


class BoilerOpcUaClient:
    """Простой клиент: connect() -> get_value()/set_value()/get_all_values() -> disconnect()."""

    def __init__(self, endpoint: str = config.OPC_ENDPOINT_CLIENT):
        self.endpoint = endpoint
        self.client = Client(endpoint)
        self.nodes = {}

    def connect(self):
        self.client.connect()
        ns = self.client.get_namespace_index(config.OPC_NAMESPACE_URI)
        objects = self.client.get_objects_node()
        self.nodes = {
            name: objects.get_child([f"{ns}:{part}" for part in path])
            for name, path in TAG_PATHS.items()
        }
        log.info("Подключено к %s, разрешено %d тегов", self.endpoint, len(self.nodes))

    def disconnect(self):
        try:
            self.client.disconnect()
        except Exception:
            pass

    def get_value(self, tag_name: str):
        return self.nodes[tag_name].get_value()

    def set_value(self, tag_name: str, value):
        if tag_name not in WRITABLE_TAGS:
            raise ValueError(f"Тег '{tag_name}' недоступен для записи")
        self.nodes[tag_name].set_value(value)

    def get_all_values(self) -> dict:
        return {name: node.get_value() for name, node in self.nodes.items()}


def validate_value(tag_name: str, value):
    """Обрезка значения по допустимому диапазону перед записью (golubeva)."""
    kind = WRITABLE_TAGS.get(tag_name)
    if kind == "bool":
        return bool(value)
    value = float(value)
    if kind == "percent":
        return max(0.0, min(100.0, value))
    if kind == "seconds":
        return max(0.1, min(120.0, value))
    if kind == "temperature":
        return max(10.0, min(95.0, value))       # верхний предел = порог блокировки перегрева
    if kind == "temperature_wide":
        return max(0.0, min(100.0, value))        # температура магистралей горячей/холодной воды
    return value


if __name__ == "__main__":
    # быстрая самопроверка: подключиться и вывести срез текущих данных
    client = BoilerOpcUaClient()
    try:
        client.connect()
        values = client.get_all_values()
        print(f"Уровень:      {values['level']:.2f} %")
        print(f"Температура:  {values['temperature']:.2f} °C")
        print(f"Давление:     {values['pressure']:.3f} бар")
        print(f"Клапан гор.:  {values['hot_valve']:.1f} %  (факт: {values['hot_valve_effective']:.1f} %)")
        print(f"Клапан хол.:  {values['cold_valve']:.1f} %  (факт: {values['cold_valve_effective']:.1f} %)")
        print(f"Клапан вых.:  {values['outlet_valve']:.1f} %")
    finally:
        client.disconnect()
