"""
Вспомогательный клиент OPC UA: подключение к серверу бойлера
и разрешение путей узлов адресного пространства в объекты Node.

Используется в history_logger.py, но может переиспользоваться
любым другим клиентским скриптом (например, дашбордом).
"""

import logging
from opcua import Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("boiler-opcua-client")

SERVER_URL = "opc.tcp://localhost:4841/boiler/server/"
NAMESPACE_URI = "http://example.org/boiler-scada"

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


def connect(server_url: str = SERVER_URL) -> Client:
    """Подключается к OPC UA серверу бойлера и возвращает клиента."""
    client = Client(server_url)
    client.connect()
    log.info("Подключились к %s", server_url)
    return client


def resolve_nodes(client: Client, namespace_uri: str = NAMESPACE_URI, tags: dict = TAGS) -> dict:
    """Разрешает символьные имена тегов в объекты Node текущей сессии."""
    ns = client.get_namespace_index(namespace_uri)
    objects = client.get_objects_node()
    return {
        name: objects.get_child([f"{ns}:{part}" for part in path])
        for name, path in tags.items()
    }


def poll_values(nodes: dict) -> dict:
    """Считывает текущие значения со всех переданных узлов одним снимком."""
    return {name: node.get_value() for name, node in nodes.items()}
