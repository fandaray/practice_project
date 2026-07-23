"""
Точка входа: запускает OPC UA сервер бойлера.

Запуск:  python server_main.py
"""

from opc_server import BoilerOpcUaServer


if __name__ == "__main__":
    BoilerOpcUaServer().run()
