# Проект: Модель бойлера с OPC UA сервером и историей

## Описание

Проект моделирует бойлер с двумя входными потоками (горячая и холодная вода) и одним выходным потоком. Управление осуществляется через регулируемые клапаны на входах и выходе.

### Структура проекта (основные файлы)
* `boiler_model.py` — модель бойлера (логика изменения уровня и температуры).
* `opc_server.py` — OPC UA сервер, который предоставляет данные модели и принимает команды (открытие клапанов).
* `server_main.py` — запускает модель и сервер, обновляет состояние каждую секунду.
* `opcua_client.py` — пример клиента, который читает данные с OPC UA сервера (например, SCADA-интерфейс).
* `history_logger.py` — отдельный процесс, который раз в 5 секунд считывает данные с OPC UA сервера и записывает в SQLite базу.

---

## ⚙️ Начальные условия модели

* **Бойлер пустой** (0% заполнения).
* **Клапаны на входе** (горячем и холодном) открыты на 50%.
* **Клапан на выходе** открыт на 100%.
* **Температура воды:** горячей — 90°C, холодной — 10°C.

---

## Технологический стек

- **Python 3.8+**
- **opcua** — библиотека для OPC UA сервера и клиента
- **SQLite** — для хранения исторических данных
- **Threading** — для параллельной работы модели, сервера и логгера
- **Visual Studio Code** — основная IDE для разработки

##  Как запустить


**1. Установить зависимости (например, библиотеку `opcua`):**
```bash
pip install opcua

**2. Запустить OPC UA сервер:  **
```bash
python run_server.py

**3. В отдельном терминале запустить модель бойлера и OPC клиент:**
```bash
python run_model.py

**4. В другом терминале запустить логирование истории:
```bash
python history_logger.py

**5. Для теста или мониторинга можно запустить клиент:**
```bash
**python opcua_client.py**
```
##  Документация и полезные ссылки

[OPC](https://github.com/fandaray/practice_project/blob/main/students/khabarov/students/khabarov/docs/opc.md).
[Flask](https://github.com/fandaray/practice_project/blob/main/students/khabarov/docs/flask.md).
[Модели](https://github.com/fandaray/practice_project/blob/main/students/khabarov/docs/models.md).
[Git](https://github.com/fandaray/practice_project/blob/main/students/khabarov/docs/git.md).
[Github flow](https://github.com/fandaray/practice_project/blob/main/students/khabarov/docs/github%20flow.md).
