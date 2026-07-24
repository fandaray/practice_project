"""
Главная точка входа (по заданию): запускает OPC UA сервер вместе с моделью
бойлера. Сама модель "живёт" внутри BoilerOpcUaServer и обновляется каждую
секунду (config.MODEL_STEP_SECONDS), как того требует задание.

Запуск:  python server_main.py
"""

from opc_server import BoilerOpcUaServer

if __name__ == "__main__":
    BoilerOpcUaServer().run()
