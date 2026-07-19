import time
from boiler_model import BoilerModel
from opcua_client import OPCBoilerClient
from pid import StandardController
from mod_pid import ModifiedController

if __name__ == "__main__":
    model = BoilerModel()
    client = OPCBoilerClient()

    std_controller = StandardController()
    mod_controller = ModifiedController()

    shutting_down = False
    shutdown_timer = 0.0
    last_auto_mode = False

    try:
        client.connect()
        print("🎛️ OPC UA клиент подключен")
        client.set_value("StartSimulation", True)

        stability_counter = 0

        while True:
            if not client.get_value("StartSimulation"):
                time.sleep(1)
                continue

            auto_mode = client.get_value("AutoMode")
            target_temp = client.get_value("TargetTemp")
            target_level = client.get_value("TargetLevel")
            controller_type = client.get_value("ControllerType")

            model.valve_in_time = client.get_value("ValveInTravelTime")
            model.valve_out_time = client.get_value("ValveOutTravelTime")

            if auto_mode and not last_auto_mode:
                shutting_down = False
                stability_counter = 0

            last_auto_mode = auto_mode

            if auto_mode:
                curr_temp = model.get_temperature()
                curr_level = model.get_level_percent()

                if controller_type == 1:
                    v_hot, v_cold, v_out = std_controller.compute(curr_temp, curr_level, target_temp, target_level,
                                                                  dt=1.0)
                else:
                    v_hot, v_cold, v_out = mod_controller.compute(curr_temp, curr_level, target_temp, target_level,
                                                                  dt=1.0)

                v_hot = min(v_hot, 0.65)
                v_cold = min(v_cold, 0.65)

                if curr_level > 85.0:
                    v_hot = v_cold = 0.05
                    v_out = 0.85

                model.valve_hot_cmd = v_hot
                model.valve_cold_cmd = v_cold
                model.valve_out_cmd = v_out

                temp_ok = abs(curr_temp - target_temp) <= 4.0
                level_ok = abs(curr_level - target_level) <= 5.0

                if temp_ok and level_ok:
                    stability_counter += 1
                else:
                    stability_counter = 0

                if stability_counter >= 10:
                    print("✅ ТАУ успешно завершила работу!")
                    print(f"   Итоговые параметры: T={curr_temp:.1f}°C | Level={curr_level:.1f}%")
                    client.set_value("AutoMode", False)
                    shutting_down = True
                    shutdown_timer = time.time()
                    stability_counter = 0

            if not auto_mode and shutting_down:
                elapsed = time.time() - shutdown_timer
                progress = min(elapsed / 25.0, 1.0)

                input_close = max(0.0, 1.0 - progress)
                output_close = max(0.0, 1.0 - (progress / 2.0))

                model.valve_hot_cmd = input_close
                model.valve_cold_cmd = input_close
                model.valve_out_cmd = output_close

                if progress >= 1.0:
                    client.set_value("ValveHotInCmd", 0.0)
                    client.set_value("ValveColdInCmd", 0.0)
                    client.set_value("ValveOutCmd", 0.0)
                    shutting_down = False

            elif not auto_mode:
                model.valve_hot_cmd = client.get_value("ValveHotInCmd")
                model.valve_cold_cmd = client.get_value("ValveColdInCmd")
                model.valve_out_cmd = client.get_value("ValveOutCmd")

            model.step(dt=1.0)

            client.set_value("ValveHotIn", model.valve_hot)
            client.set_value("ValveColdIn", model.valve_cold)
            client.set_value("ValveOut", model.valve_out)
            client.set_value("OutputTemp", model.get_temperature())
            client.set_value("WaterLevel", model.get_level_percent())

            time.sleep(1)

    except KeyboardInterrupt:
        print("🛑 Остановка модели...")
    finally:
        client.set_value("StartSimulation", False)
        client.disconnect()
        print("🔌 Клиент отключён")