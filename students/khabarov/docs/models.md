# Модели (Models) — Полное руководство

## Что такое "Модель" в контексте проекта?

**Модель** — это **математическая и программная реализация** физического объекта (в данном случае — бойлера).  
Она описывает поведение системы: как изменяется уровень воды и температура в зависимости от положения клапанов, входных температур и времени.

Модель отделена от OPC UA сервера и клиента — это ключевой принцип **чистой архитектуры**.

---

## Виды моделей в промышленной автоматизации

| Вид модели              | Описание                                      | Применение                          | Сложность |
|-------------------------|-----------------------------------------------|-------------------------------------|---------|
| **Математическая**      | Формулы, дифференциальные уравнения          | Точные расчёты                      | Высокая |
| **Симуляционная**       | Пошаговое моделирование (step-by-step)        | Реальное время, обучение            | Средняя |
| **Физическая**          | Эмуляция реального оборудования               | Тестирование                        | Высокая |
| **Data-Driven**         | На основе машинного обучения                  | Предсказательная аналитика          | Высокая |
| **Гибридная**           | Комбинация математической + симуляционной     | **Наш проект**                      | Средняя |

В вашем проекте используется **гибридная симуляционная модель**.

---

## Структура модели бойлера (boiler_model.py)

### Основные параметры модели:
- `level` — текущий уровень воды (0–100%)
- `temperature` — температура воды в бойлере
- `valve_hot` — положение горячего клапана (0–1)
- `valve_cold` — положение холодного клапана (0–1)
- `valve_out` — положение выходного клапана (0–1)
- `temp_hot` — температура горячей воды (обычно 80–90°C)
- `temp_cold` — температура холодной воды (обычно 10–20°C)

---

## Плюсы и минусы подхода

### Плюсы:
- **Чистый код** — модель не знает про OPC UA
- **Легко тестировать** в отрыве от сервера
- **Повторное использование** модели
- **Простота отладки**
- **Возможность улучшения** математической точности
- **Хорошо интегрируется** с Flask, OPC UA, историей

### Минусы:
- Упрощённая физика (не учитывает все реальные процессы)
- Задержка в 1 секунду (можно улучшить)
- Не учитывает тепловые потери в окружающую среду
- Нет модели давления

---

## Пример кода: boiler_model.py (ПОМЕНЯТЬ!!!)

```python
# boiler_model.py
import time

class BoilerModel:
    def __init__(self):
        # Начальные условия
        self.level = 0.0                    # Процент заполнения (0-100)
        self.temperature = 20.0             # Температура в бойлере (°C)
        
        # Клапаны (0.0 - 1.0)
        self.valve_hot = 0.5
        self.valve_cold = 0.5
        self.valve_out = 1.0
        
        # Температуры входов
        self.temp_hot = 80.0
        self.temp_cold = 20.0
        
        # Параметры модели
        self.max_volume = 100.0             # Условный объём бойлера
        self.flow_rate = 15.0               # Базовая скорость потока (л/сек)
        self.heat_loss_factor = 0.005       # Потери тепла в окружающую среду

    def step(self, dt=1.0):
        """Один шаг симуляции"""
        # Расчёт входного потока
        hot_inflow = self.valve_hot * self.flow_rate * dt
        cold_inflow = self.valve_cold * self.flow_rate * dt
        total_inflow = hot_inflow + cold_inflow
        
        # Выходной поток
        outflow = self.valve_out * self.flow_rate * dt
        
        # Обновление уровня
        self.level += (total_inflow - outflow)
        self.level = max(0.0, min(100.0, self.level))
        
        # Обновление температуры
        if total_inflow > 0:
            weighted_temp = (hot_inflow * self.temp_hot + cold_inflow * self.temp_cold) / total_inflow
            self.temperature = (self.temperature * 0.85 + weighted_temp * 0.15)
        
        # Тепловые потери
        self.temperature -= self.heat_loss_factor * dt
        self.temperature = max(10.0, self.temperature)

    def get_level_percent(self):
        return round(self.level, 2)

    def get_temperature(self):
        return round(self.temperature, 2)

    def set_valves(self, hot=0.5, cold=0.5, out=1.0):
        self.valve_hot = max(0.0, min(1.0, hot))
        self.valve_cold = max(0.0, min(1.0, cold))
        self.valve_out = max(0.0, min(1.0, out))

    def reset(self):
        """Сброс модели в начальное состояние"""
        self.level = 0.0
        self.temperature = 20.0
        self.valve_hot = 0.5
        self.valve_cold = 0.5
        self.valve_out = 1.0

## run_model.py (ПОМЕНЯТЬ!!!)

```python
# run_model.py
import time
from boiler_model import BoilerModel
from opcua_client import OPCBoilerClient

if __name__ == "__main__":
    model = BoilerModel()
    client = OPCBoilerClient()
    
    try:
        client.connect()
        print("🎛️ OPC UA клиент успешно подключен")
        
        # Запуск симуляции
        client.set_value("StartSimulation", True)
        print("🚀 Моделирование запущено")
        
        # Инициализация клапанов
        model.set_valves(hot=0.5, cold=0.5, out=1.0)
        client.set_value("ValveHotIn", model.valve_hot)
        client.set_value("ValveColdIn", model.valve_cold)
        client.set_value("ValveOut", model.valve_out)
        
        print("🔄 Основной цикл моделирования запущен. Нажмите Ctrl+C для остановки.")
        
        while True:
            # Проверка флага запуска
            if not client.get_value("StartSimulation"):
                print("⏸ Моделирование приостановлено")
                time.sleep(1)
                continue
            
            # Чтение актуальных значений клапанов из OPC UA
            model.valve_hot = client.get_value("ValveHotIn")
            model.valve_cold = client.get_value("ValveColdIn")
            model.valve_out = client.get_value("ValveOut")
            
            # Фиксированные температуры входов
            model.temp_hot = 80.0
            model.temp_cold = 20.0
            
            # Выполняем шаг модели
            model.step(dt=1.0)
            
            # Запись результатов в OPC UA сервер
            client.set_value("InputTempHot", model.temp_hot)
            client.set_value("InputTempCold", model.temp_cold)
            client.set_value("OutputTemp", model.get_temperature())
            client.set_value("WaterLevel", model.get_level_percent())
            
            # Логирование в консоль
            print(f"[{time.strftime('%H:%M:%S')}] "
                  f"Уровень: {model.get_level_percent():6.1f}% | "
                  f"Темп: {model.get_temperature():5.1f}°C | "
                  f"Клапаны: H={model.valve_hot:.2f} C={model.valve_cold:.2f} Out={model.valve_out:.2f}")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Остановка моделирования...")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        client.set_value("StartSimulation", False)
        client.disconnect()
        print("🔌 OPC UA клиент отключён. Модель остановлена.")

    