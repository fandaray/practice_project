# Boiler SCADA — OPC UA симулятор бойлера смешения

Студент: Рихельгоф

## Описание

Симулятор промышленного объекта — бойлера смешения горячей и холодной воды —
с публикацией измерений и уставок через OPC UA.

- `src/boiler_model.py` — физическая модель бойлера (баланс массы/энергии,
  давление), технологические блокировки по уровню и температуре, авторегуляторы
  уровня и температуры.
- `src/opc_server.py` — класс OPC UA сервера: строит адресное пространство
  (Measurements/Setpoints/Alarms/Interlocks/Effective) и на каждом шаге
  прогоняет модель и публикует новые значения.
- `src/server_main.py` — точка входа, запускающая OPC UA сервер.
- `src/opcua_client.py` — переиспользуемый OPC UA клиент: подключение и
  разрешение путей узлов адресного пространства.
- `src/history_logger.py` — периодически опрашивает сервер через
  `opcua_client` и пишет историю параметров в SQLite.

## Запуск

```
pip install -r requirements.txt
cd src
python server_main.py        # в одном терминале — сервер
python history_logger.py     # в другом терминале — логирование истории
```

## Запуск в Docker

```
docker build -t boiler-scada .
docker run -p 4841:4841 boiler-scada
```

## Полная версия проекта

Расширенная версия (с веб-панелью SCADA/HMI на Flask) доступна отдельно:
https://github.com/Surevio/opcua-boiler-scada
