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

        stability_counter = 0

        while True:
            if not client.get_value("StartSimulation"):
                time.sleep(1)
                continue

            auto_mode = client.get_value("AutoMode")
            target_temp = client.get_value("TargetTemp")
            target_level = client.get_value("TargetLevel")

            model.valve_in_time = client.get_value("ValveInTravelTime")
            model.valve_out_time = client.get_value("ValveOutTravelTime")

            if auto_mode:
                try:
                    model.set_targets(target_temp, target_level)

                    curr_temp = model.get_temperature()
                    curr_level = model.get_level_percent()

                    if abs(curr_temp - target_temp) <= 5.0 and abs(curr_level - target_level) <= 5.0:
                        stability_counter += 1
                    else:
                        stability_counter = 0

                    if stability_counter >= 5:
                        print("✅ Уставки достигнуты. ТАУ отключается.")
                        client.set_value("AutoMode", False)
                        model.disable_auto()
                        stability_counter = 0

                except ValueError as e:
                    print(e)
                    client.set_value("AutoMode", False)
                    model.disable_auto()
            else:
                stability_counter = 0
                model.disable_auto()
                model.valve_hot_cmd = client.get_value("ValveHotInCmd")
                model.valve_cold_cmd = client.get_value("ValveColdInCmd")
                model.valve_out_cmd = client.get_value("ValveOutCmd")

            model.step(dt=1.0)

            client.set_value("ValveHotIn", model.valve_hot)
            client.set_value("ValveColdIn", model.valve_cold)
            client.set_value("ValveOut", model.valve_out)
            client.set_value("InputTempHot", model.temp_hot)
            client.set_value("InputTempCold", model.temp_cold)
            client.set_value("OutputTemp", model.get_temperature())
            client.set_value("WaterLevel", model.get_level_percent())

            time.sleep(1)

    except KeyboardInterrupt:
        print("🛑 Остановка модели...")
    finally:
        client.set_value("StartSimulation", False)  # 👈 Остановить по завершению
        client.disconnect()
        print("🔌 Клиент отключён")