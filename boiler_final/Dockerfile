FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

# Внутри контейнера src/ копируется "плоско" в /app (как требует шаблон
# задания), поэтому вычисление пути к БД через parent.parent относительно
# файла config.py указало бы за пределы /app. Явно фиксируем путь здесь -
# он совпадает с точкой монтирования тома в docker-compose.yml.
ENV DB_FILE=/app/data/boiler_history.sqlite3
RUN mkdir -p /app/data

# Порт OPC UA сервера по заданию
EXPOSE 4840
# Порт веб-панели SCADA (app.py)
EXPOSE 5050

# По умолчанию запускается OPC UA сервер с моделью бойлера.
# Чтобы запустить веб-панель или логгер истории в отдельном контейнере,
# переопределите команду при запуске (см. README.md и docker-compose.yml):
#   docker run <image> python app.py
#   docker run <image> python history_logger.py
CMD ["python", "server_main.py"]
