"""
OPC UA сервер бойлера.

Архитектура адресного пространства и логика работы (авторегуляторы,
технологические блокировки) - решение rikhelgof (студент).

Публикует адресное пространство:

  Boiler/
    Measurements/
      Level             (Double,  ro) - уровень воды, %
      Temperature       (Double,  ro) - температура смеси, °C
      TemperatureValid  (Boolean, ro) - False, если в баке нет воды и мерить нечего
      Pressure          (Double,  ro) - давление, бар
    Setpoints/
      HotValve          (Double,  rw) - открытие клапана горячей воды, %
      ColdValve         (Double,  rw) - открытие клапана холодной воды, %
      OutletValve       (Double,  rw) - открытие сливного клапана, %
      Heater            (Double,  rw) - мощность нагревателя, %
      ValveTravelTime   (Double,  rw) - время полного хода клапана, сек (khabarov)
      LevelSetpoint     (Double,  rw) - целевой уровень для авторегулятора, %
      LevelAuto         (Boolean, rw) - включить авторегулирование уровня
      TemperatureSetpoint (Double, rw) - целевая температура для авторегулятора, °C
      TemperatureAuto   (Boolean, rw) - включить авторегулирование температуры
      InputTempHot      (Double,  rw) - температура горячей магистрали, °C
      InputTempCold     (Double,  rw) - температура холодной магистрали, °C
    Alarms/
      LevelHigh         (Boolean, ro)
      LevelLow          (Boolean, ro)
      OverTemperature    (Boolean, ro)
    Interlocks/
      Overflow          (Boolean, ro) - сработала защита от переполнения
      Overtemp          (Boolean, ro) - сработала защита от перегрева
    Effective/
      HotValve          (Double, ro) - фактическое положение клапана горячей воды, %
      ColdValve         (Double, ro) - фактическое положение клапана холодной воды, %
      Heater            (Double, ro) - фактическая мощность нагревателя, %
      (отличается от Setpoints, если клапан ещё "едет" к уставке или сработала блокировка)

Каждую секунду (MODEL_STEP_SECONDS) сервер:
  1. читает уставки клапанов/нагревателя/температур из адресного пространства,
  2. прогоняет шаг модели,
  3. публикует новые измерения, алармы и эффективные положения.

Порт 4840 - согласно заданию.

Запуск:  python opc_server.py
"""

import logging
import time

from opcua import Server, ua

import config
from boiler_model import BoilerModel

logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("opcua").setLevel(logging.WARNING)
log = logging.getLogger("boiler-opcua-server")


class BoilerOpcUaServer:
    def __init__(self, endpoint: str = config.OPC_ENDPOINT):
        self.model = BoilerModel()
        self.server = Server()
        self.server.set_endpoint(endpoint)
        self.server.set_server_name("Boiler SCADA Simulation Server")

        self.idx = self.server.register_namespace(config.OPC_NAMESPACE_URI)
        self._build_address_space()

    def _build_address_space(self):
        objects = self.server.get_objects_node()
        boiler = objects.add_object(self.idx, "Boiler")

        measurements = boiler.add_object(self.idx, "Measurements")
        self.n_level = measurements.add_variable(self.idx, "Level", 0.0, ua.VariantType.Double)
        self.n_temp = measurements.add_variable(self.idx, "Temperature", 0.0, ua.VariantType.Double)
        self.n_temp_valid = measurements.add_variable(self.idx, "TemperatureValid", True, ua.VariantType.Boolean)
        self.n_pressure = measurements.add_variable(self.idx, "Pressure", 0.0, ua.VariantType.Double)
        for node in (self.n_level, self.n_temp, self.n_temp_valid, self.n_pressure):
            node.set_writable(False)

        setpoints = boiler.add_object(self.idx, "Setpoints")
        s = self.model.state
        self.n_hot_valve = setpoints.add_variable(self.idx, "HotValve", s.hot_valve_pct, ua.VariantType.Double)
        self.n_cold_valve = setpoints.add_variable(self.idx, "ColdValve", s.cold_valve_pct, ua.VariantType.Double)
        self.n_outlet_valve = setpoints.add_variable(self.idx, "OutletValve", s.outlet_valve_pct, ua.VariantType.Double)
        self.n_heater = setpoints.add_variable(self.idx, "Heater", s.heater_pct, ua.VariantType.Double)
        self.n_valve_travel_time = setpoints.add_variable(
            self.idx, "ValveTravelTime", self.model.params.valve_travel_time_s, ua.VariantType.Double
        )
        self.n_input_temp_hot = setpoints.add_variable(
            self.idx, "InputTempHot", self.model.params.hot_supply_temp_c, ua.VariantType.Double
        )
        self.n_input_temp_cold = setpoints.add_variable(
            self.idx, "InputTempCold", self.model.params.cold_supply_temp_c, ua.VariantType.Double
        )
        for node in (
            self.n_hot_valve, self.n_cold_valve, self.n_outlet_valve, self.n_heater,
            self.n_valve_travel_time, self.n_input_temp_hot, self.n_input_temp_cold,
        ):
            node.set_writable(True)

        # --- автоматическое регулирование: пока включено, регулятор сам считает
        #     клапаны/нагреватель и перезаписывает узлы выше (rikhelgof) ---
        self.n_level_sp = setpoints.add_variable(self.idx, "LevelSetpoint", 50.0, ua.VariantType.Double)
        self.n_level_auto = setpoints.add_variable(self.idx, "LevelAuto", False, ua.VariantType.Boolean)
        self.n_temp_sp = setpoints.add_variable(self.idx, "TemperatureSetpoint", 60.0, ua.VariantType.Double)
        self.n_temp_auto = setpoints.add_variable(self.idx, "TemperatureAuto", False, ua.VariantType.Boolean)
        for node in (self.n_level_sp, self.n_level_auto, self.n_temp_sp, self.n_temp_auto):
            node.set_writable(True)

        alarms = boiler.add_object(self.idx, "Alarms")
        self.n_level_high = alarms.add_variable(self.idx, "LevelHigh", False, ua.VariantType.Boolean)
        self.n_level_low = alarms.add_variable(self.idx, "LevelLow", False, ua.VariantType.Boolean)
        self.n_overtemp = alarms.add_variable(self.idx, "OverTemperature", False, ua.VariantType.Boolean)
        for node in (self.n_level_high, self.n_level_low, self.n_overtemp):
            node.set_writable(False)

        interlocks = boiler.add_object(self.idx, "Interlocks")
        self.n_il_overflow = interlocks.add_variable(self.idx, "Overflow", False, ua.VariantType.Boolean)
        self.n_il_overtemp = interlocks.add_variable(self.idx, "Overtemp", False, ua.VariantType.Boolean)
        for node in (self.n_il_overflow, self.n_il_overtemp):
            node.set_writable(False)

        effective = boiler.add_object(self.idx, "Effective")
        self.n_hot_valve_eff = effective.add_variable(self.idx, "HotValve", 0.0, ua.VariantType.Double)
        self.n_cold_valve_eff = effective.add_variable(self.idx, "ColdValve", 0.0, ua.VariantType.Double)
        self.n_heater_eff = effective.add_variable(self.idx, "Heater", 0.0, ua.VariantType.Double)
        for node in (self.n_hot_valve_eff, self.n_cold_valve_eff, self.n_heater_eff):
            node.set_writable(False)

        log.info("Адресное пространство создано, namespace index=%d", self.idx)

    def _apply_setpoints_from_space(self):
        m = self.model
        m.set_hot_valve(self.n_hot_valve.get_value())
        m.set_cold_valve(self.n_cold_valve.get_value())
        m.set_outlet_valve(self.n_outlet_valve.get_value())
        m.set_heater(self.n_heater.get_value())
        m.set_valve_travel_time(self.n_valve_travel_time.get_value())
        m.params.hot_supply_temp_c = self.n_input_temp_hot.get_value()
        m.params.cold_supply_temp_c = self.n_input_temp_cold.get_value()
        m.set_level_setpoint(self.n_level_sp.get_value())
        m.set_level_auto(self.n_level_auto.get_value())
        m.set_temperature_setpoint(self.n_temp_sp.get_value())
        m.set_temperature_auto(self.n_temp_auto.get_value())

    def _publish_state(self):
        s = self.model.state
        self.n_level.set_value(round(s.level_pct, 2))
        self.n_temp.set_value(round(s.temperature_c, 2))
        self.n_temp_valid.set_value(s.temperature_valid)
        self.n_pressure.set_value(round(s.pressure_bar, 3))
        self.n_level_high.set_value(s.level_high_alarm)
        self.n_level_low.set_value(s.level_low_alarm)
        self.n_overtemp.set_value(s.overtemp_alarm)

        self.n_il_overflow.set_value(s.interlock_overflow)
        self.n_il_overtemp.set_value(s.interlock_overtemp)

        self.n_hot_valve_eff.set_value(round(s.hot_valve_effective_pct, 1))
        self.n_cold_valve_eff.set_value(round(s.cold_valve_effective_pct, 1))
        self.n_heater_eff.set_value(round(s.heater_effective_pct, 1))

        # если включено авторегулирование - модель сама пересчитала *_pct поверх
        # ручных значений; записываем это обратно в узлы Setpoints, иначе на
        # следующем цикле _apply_setpoints_from_space() затрёт расчёт регулятора
        # устаревшим значением узла (rikhelgof)
        self.n_hot_valve.set_value(round(s.hot_valve_pct, 1))
        self.n_cold_valve.set_value(round(s.cold_valve_pct, 1))
        self.n_outlet_valve.set_value(round(s.outlet_valve_pct, 1))
        self.n_heater.set_value(round(s.heater_pct, 1))

    def run(self):
        self.server.start()
        log.info("OPC UA сервер бойлера запущен: %s", config.OPC_ENDPOINT)
        dt = config.MODEL_STEP_SECONDS
        try:
            while True:
                self._apply_setpoints_from_space()
                self.model.step(dt)
                self._publish_state()
                time.sleep(dt)
        except KeyboardInterrupt:
            log.info("Остановка по Ctrl+C")
        finally:
            self.server.stop()
            log.info("OPC UA сервер остановлен")


if __name__ == "__main__":
    BoilerOpcUaServer().run()
