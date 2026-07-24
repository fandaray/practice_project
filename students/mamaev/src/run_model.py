import time
from boiler_model import BoilerModel
from opcua_client import OPCBoilerClient

if __name__ == "__main__":
    model = BoilerModel()
    client = OPCBoilerClient()

    try:
        client.connect()
        print("🎛️ OPC UA клиент подключен")

        client.set_value("StartSimulation", True)
        print("🚀 Моделирование запущено (StartSimulation = True)")

        # Начальные значения
        model.valve_hot = 0.5
        model.valve_cold = 0.5
        model.valve_out = 1.0

        client.set_value("ValveHotIn", model.valve_hot)
        client.set_value("ValveColdIn", model.valve_cold)
        client.set_value("ValveOut", model.valve_out)

        emergency_active = False
        saved_valves = {}
        manual_change = False

        # Параметры регулятора
        Kp_level = 0.025
        Kp_temp = 6.0
        Ki_temp = 0.08

        # Переменные состояния автоматики
        auto_active = False
        integral_temp = 0.0
        target_reached = False  # флаг, что уставки достигнуты
        locked_valves = {}      # сохранённые положения клапанов после достижения целей
        stable_counter = 0      # счётчик для подтверждения стабильности

        # Минимальный отток в режиме стабилизации
        STABLE_OUTFLOW = 0.20   # 20%

        while True:
            if not client.get_value("StartSimulation"):
                print("⏸ Ожидание запуска моделирования (StartSimulation = False)")
                time.sleep(1)
                continue

            # Чтение текущих значений
            current_hot = client.get_value("ValveHotIn")
            current_cold = client.get_value("ValveColdIn")
            current_out = client.get_value("ValveOut")
            water_level = client.get_value("WaterLevel")
            output_temp = client.get_value("OutputTemp")

            setpoint_temp = client.get_value("SetpointTemperature")
            setpoint_level = client.get_value("SetpointLevel")
            auto_mode = client.get_value("AutoMode")   # запрос на включение автоматики

            # Аварийная логика (без изменений)
            if not emergency_active and water_level >= 98.0:
                saved_valves = {
                    "ValveHotIn": current_hot,
                    "ValveColdIn": current_cold,
                    "ValveOut": current_out
                }
                emergency_active = True
                manual_change = False
                client.set_value("ValveHotIn", 0.0)
                client.set_value("ValveColdIn", 0.0)
                client.set_value("ValveOut", 1.0)
                current_hot = 0.0
                current_cold = 0.0
                current_out = 1.0
                print("🚨 Авария! Переполнение бойлера! Клапаны закрыты/открыты.")
                # Сбрасываем автоматику при аварии
                auto_active = False
                target_reached = False
                integral_temp = 0.0
                locked_valves = {}
                stable_counter = 0
            elif emergency_active:
                if (abs(current_hot - 0.0) > 0.001 or
                    abs(current_cold - 0.0) > 0.001 or
                    abs(current_out - 1.0) > 0.001):
                    manual_change = True

                if water_level <= 80.0:
                    if not manual_change:
                        client.set_value("ValveHotIn", saved_valves["ValveHotIn"])
                        client.set_value("ValveColdIn", saved_valves["ValveColdIn"])
                        client.set_value("ValveOut", saved_valves["ValveOut"])
                        current_hot = saved_valves["ValveHotIn"]
                        current_cold = saved_valves["ValveColdIn"]
                        current_out = saved_valves["ValveOut"]
                        print("✅ Восстановлены предыдущие параметры клапанов.")
                    else:
                        print("ℹ️ Ручные изменения обнаружены – восстановление отменено.")
                    emergency_active = False
                    manual_change = False
                    saved_valves = {}
                    # После снятия аварии, если авто режим включён, нужно перезапустить автоматику
                    if auto_mode:
                        auto_active = True
                        target_reached = False
                        integral_temp = 0.0
                        stable_counter = 0
            else:
                # Обработка включения/выключения автоматики
                if auto_mode and not auto_active:
                    # Включаем автоматику – сбрасываем все состояния
                    auto_active = True
                    target_reached = False
                    integral_temp = 0.0
                    stable_counter = 0
                    locked_valves = {}
                    print("🔄 Автоматика включена, начало регулирования.")
                elif not auto_mode and auto_active:
                    # Выключаем автоматику – переходим в ручной режим (ничего не меняем)
                    auto_active = False
                    target_reached = False
                    integral_temp = 0.0
                    stable_counter = 0
                    print("🔄 Автоматика выключена, ручной режим.")

                # Если автоматика активна, выполняем регулирование
                if auto_active:
                    # Проверяем, достигнуты ли уставки с заданной точностью
                    tolerance_level = max(1.0, 0.03 * setpoint_level)
                    tolerance_temp = max(0.5, 0.03 * setpoint_temp)

                    error_level = setpoint_level - water_level
                    error_temp = setpoint_temp - output_temp

                    if (abs(error_level) < tolerance_level and abs(error_temp) < tolerance_temp):
                        stable_counter += 1
                    else:
                        stable_counter = 0

                    # Если стабильность держится 5 циклов (5 секунд), фиксируем режим
                    if stable_counter >= 5 and not target_reached:
                        target_reached = True
                        # Запоминаем текущие положения клапанов (кроме выходного, его выставим на 20%)
                        locked_valves = {
                            "ValveHotIn": current_hot,
                            "ValveColdIn": current_cold,
                        }
                        # Устанавливаем выходной клапан на 20%
                        client.set_value("ValveOut", STABLE_OUTFLOW)
                        current_out = STABLE_OUTFLOW
                        print("🎯 Уставки достигнуты! Переход в режим стабилизации.")
                        # Можно также скорректировать входные клапаны для поддержания баланса, но пока оставим как есть

                    if target_reached:
                        # Режим стабилизации: поддерживаем зафиксированные значения, но допускаем небольшие корректировки
                        # Проверяем, не вышли ли параметры за пределы допуска
                        if abs(error_level) > tolerance_level * 1.5 or abs(error_temp) > tolerance_temp * 1.5:
                            # Если вышли слишком сильно – переходим обратно в режим регулирования
                            target_reached = False
                            stable_counter = 0
                            integral_temp = 0.0
                            print("⚠️ Параметры вышли за допуск, возобновляем регулирование.")
                        else:
                            # Поддерживаем зафиксированные значения, но с небольшой адаптацией
                            # Можно плавно подстраивать входные клапаны для компенсации дрейфа
                            # Для простоты оставляем как есть, только слегка корректируем, если есть отклонение
                            if abs(error_level) > tolerance_level * 0.5:
                                # Коррекция уровня
                                correction = error_level * 0.01
                                new_hot = max(0.0, min(1.0, locked_valves["ValveHotIn"] + correction))
                                new_cold = max(0.0, min(1.0, locked_valves["ValveColdIn"] - correction))  # например, противовес
                                client.set_value("ValveHotIn", new_hot)
                                client.set_value("ValveColdIn", new_cold)
                                locked_valves["ValveHotIn"] = new_hot
                                locked_valves["ValveColdIn"] = new_cold
                                current_hot = new_hot
                                current_cold = new_cold
                                # Выходной клапан остаётся на 20%
                            if abs(error_temp) > tolerance_temp * 0.5:
                                # Коррекция температуры (меняем долю горячей)
                                correction = error_temp * 0.005
                                new_hot = max(0.0, min(1.0, locked_valves["ValveHotIn"] + correction))
                                new_cold = max(0.0, min(1.0, locked_valves["ValveColdIn"] - correction))
                                client.set_value("ValveHotIn", new_hot)
                                client.set_value("ValveColdIn", new_cold)
                                locked_valves["ValveHotIn"] = new_hot
                                locked_valves["ValveColdIn"] = new_cold
                                current_hot = new_hot
                                current_cold = new_cold
                            # Печатаем состояние стабилизации
                            print(f"🔒 Стабилизация: T={output_temp:.1f}°C, Level={water_level:.1f}%, "
                                  f"Клапаны: H={current_hot:.2f}, C={current_cold:.2f}, O={current_out:.2f}")
                            # Пропускаем основную логику регулирования
                    else:
                        # Режим регулирования (ПИ-регулятор)
                        # --- Регулирование уровня (П-регулятор) ---
                        # Выходной клапан пока не фиксирован, регулируем отток для уровня
                        # Но после достижения целей мы перейдём на фиксированный отток 20%
                        if abs(error_level) < tolerance_level:
                            inflow = 0.02  # минимальный приток
                            outflow = 0.02
                        elif error_level > 0:
                            inflow = min(1.0, 0.02 + abs(error_level) * Kp_level)
                            outflow = 0.02
                        else:
                            inflow = 0.02
                            outflow = min(1.0, 0.02 + abs(error_level) * Kp_level)

                        # --- Регулирование температуры (ПИ-регулятор) ---
                        integral_temp += Ki_temp * error_temp
                        integral_temp = max(-0.5, min(0.5, integral_temp))

                        if abs(error_temp) < tolerance_temp:
                            hot_fraction = 0.5
                            integral_temp = 0.0
                        else:
                            hot_fraction = 0.5 + (error_temp * Kp_temp + integral_temp) * 0.01
                            hot_fraction = max(0.0, min(1.0, hot_fraction))

                        # Дополнительная коррекция
                        if error_temp > tolerance_temp and error_level > -tolerance_level:
                            inflow = min(0.5, inflow + 0.05)
                        elif error_temp < -tolerance_temp and error_level < tolerance_level:
                            outflow = min(1.0, outflow + 0.05)

                        new_hot = inflow * hot_fraction
                        new_cold = inflow * (1 - hot_fraction)
                        new_out = outflow

                        # Ограничения
                        new_hot = max(0.0, min(1.0, new_hot))
                        new_cold = max(0.0, min(1.0, new_cold))
                        new_out = max(0.0, min(1.0, new_out))

                        # Записываем в OPC UA
                        client.set_value("ValveHotIn", new_hot)
                        client.set_value("ValveColdIn", new_cold)
                        client.set_value("ValveOut", new_out)

                        current_hot = new_hot
                        current_cold = new_cold
                        current_out = new_out

                        print(f"🔄 Регулирование: T_set={setpoint_temp}°C, T_out={output_temp:.1f}°C, "
                              f"Level_set={setpoint_level}%, Level={water_level:.1f}%, "
                              f"Клапаны: H={new_hot:.2f}, C={new_cold:.2f}, O={new_out:.2f}")

            # Передаём в модель
            model.valve_hot = current_hot
            model.valve_cold = current_cold
            model.valve_out = current_out

            model.temp_hot = 90.0
            model.temp_cold = 20.0
            model.step()

            client.set_value("InputTempHot", model.temp_hot)
            client.set_value("InputTempCold", model.temp_cold)
            client.set_value("OutputTemp", model.get_temperature())
            client.set_value("WaterLevel", model.get_level_percent())

            time.sleep(1)

    except KeyboardInterrupt:
        print("🛑 Остановка модели...")
    finally:
        client.set_value("StartSimulation", False)
        client.disconnect()
        print("🔌 Клиент отключён")