"""
OPC UA сервер бойлера.

Публикует адресное пространство:

  Boiler/
    Measurements/
      Level          (Double, ro)  - уровень воды, %
      Temperature    (Double, ro)  - температура смеси, °C
      TemperatureValid (Boolean, ro) - False, если в баке нет воды и мерить нечего
      Pressure       (Double, ro)  - давление, бар
    Setpoints/
      HotValve       (Double, rw)  - открытие клапана горячей воды, %
      ColdValve      (Double, rw)  - открытие клапана холодной воды, %
      OutletValve    (Double, rw)  - открытие сливного клапана, %
      Heater         (Double, rw)  - мощность нагревателя, %
      LevelSetpoint      (Double, rw)  - целевой уровень для авторегулятора, %
      LevelAuto          (Boolean, rw) - включить авторегулирование уровня
      TemperatureSetpoint(Double, rw)  - целевая температура для авторегулятора, °C
      TemperatureAuto    (Boolean, rw) - включить авторегулирование температуры
      (пока Auto включён, регулятор сам считает и перезаписывает HotValve/ColdValve/
       OutletValve/Heater - значения, пришедшие от оператора, игнорируются)
    Alarms/
      LevelHigh      (Boolean, ro)
      LevelLow       (Boolean, ro)
      OverTemperature(Boolean, ro)
    Interlocks/
      Overflow       (Boolean, ro)  - сработала защита от переполнения
      Overtemp       (Boolean, ro)  - сработала защита от перегрева
    Effective/
      HotValve       (Double, ro)  - фактическое положение клапана горячей воды, %
      ColdValve      (Double, ro)  - фактическое положение клапана холодной воды, %
      Heater         (Double, ro)  - фактическая мощность нагревателя, %
      (может отличаться от Setpoints, если сработала блокировка из Interlocks)

Каждые SCAN_PERIOD_S секунд сервер:
  1. читает текущие уставки клапанов/нагревателя из адресного пространства,
  2. прогоняет шаг модели,
  3. публикует новые измерения и алармы.

Запуск:  python -m server.opcua_server
"""

import time
import logging
import threading

from opcua import Server, ua

from boiler_core.model import BoilerModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("boiler-opcua-server")

ENDPOINT = "opc.tcp://0.0.0.0:4841/boiler/server/"
NAMESPACE_URI = "http://example.org/boiler-scada"
SCAN_PERIOD_S = 1.0


class BoilerOpcUaServer:
    def __init__(self, endpoint: str = ENDPOINT):
        self.model = BoilerModel()
        self.server = Server()
        self.server.set_endpoint(endpoint)
        self.server.set_server_name("Boiler SCADA Simulation Server")

        self.idx = self.server.register_namespace(NAMESPACE_URI)
        self._build_address_space()
        self._stop_event = threading.Event()

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
        self.n_hot_valve = setpoints.add_variable(self.idx, "HotValve", 0.0, ua.VariantType.Double)
        self.n_cold_valve = setpoints.add_variable(self.idx, "ColdValve", 0.0, ua.VariantType.Double)
        self.n_outlet_valve = setpoints.add_variable(self.idx, "OutletValve", 0.0, ua.VariantType.Double)
        self.n_heater = setpoints.add_variable(self.idx, "Heater", 0.0, ua.VariantType.Double)
        for node in (self.n_hot_valve, self.n_cold_valve, self.n_outlet_valve, self.n_heater):
            node.set_writable(True)

        # --- автоматическое регулирование: пока включено, регулятор сам считает
        #     клапаны/нагреватель и перезаписывает узлы выше ---
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

        # --- технологические блокировки: срабатывают автоматически поверх
        #     уставок оператора и защищают оборудование ---
        interlocks = boiler.add_object(self.idx, "Interlocks")
        self.n_il_overflow = interlocks.add_variable(self.idx, "Overflow", False, ua.VariantType.Boolean)
        self.n_il_overtemp = interlocks.add_variable(self.idx, "Overtemp", False, ua.VariantType.Boolean)
        for node in (self.n_il_overflow, self.n_il_overtemp):
            node.set_writable(False)

        # фактическое положение исполнительных механизмов (после наложения блокировок) -
        # может отличаться от Setpoints, если блокировка принудительно их скорректировала
        effective = boiler.add_object(self.idx, "Effective")
        self.n_hot_valve_eff = effective.add_variable(self.idx, "HotValve", 0.0, ua.VariantType.Double)
        self.n_cold_valve_eff = effective.add_variable(self.idx, "ColdValve", 0.0, ua.VariantType.Double)
        self.n_heater_eff = effective.add_variable(self.idx, "Heater", 0.0, ua.VariantType.Double)
        for node in (self.n_hot_valve_eff, self.n_cold_valve_eff, self.n_heater_eff):
            node.set_writable(False)

    def _apply_setpoints_from_space(self):
        self.model.set_hot_valve(self.n_hot_valve.get_value())
        self.model.set_cold_valve(self.n_cold_valve.get_value())
        self.model.set_outlet_valve(self.n_outlet_valve.get_value())
        self.model.set_heater(self.n_heater.get_value())
        self.model.set_level_setpoint(self.n_level_sp.get_value())
        self.model.set_level_auto(self.n_level_auto.get_value())
        self.model.set_temperature_setpoint(self.n_temp_sp.get_value())
        self.model.set_temperature_auto(self.n_temp_auto.get_value())

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
        # устаревшим значением узла. В ручном режиме это просто безвредная
        # запись того же значения, которое было только что прочитано.
        self.n_hot_valve.set_value(round(s.hot_valve_pct, 1))
        self.n_cold_valve.set_value(round(s.cold_valve_pct, 1))
        self.n_outlet_valve.set_value(round(s.outlet_valve_pct, 1))
        self.n_heater.set_value(round(s.heater_pct, 1))

    def run(self):
        self.server.start()
        log.info("OPC UA сервер бойлера запущен: %s", ENDPOINT)
        log.info("Namespace index: %d", self.idx)
        try:
            while not self._stop_event.is_set():
                self._apply_setpoints_from_space()
                self.model.step(SCAN_PERIOD_S)
                self._publish_state()
                time.sleep(SCAN_PERIOD_S)
        except KeyboardInterrupt:
            log.info("Остановка по Ctrl+C")
        finally:
            self.server.stop()
            log.info("OPC UA сервер остановлен")

    def stop(self):
        self._stop_event.set()


if __name__ == "__main__":
    BoilerOpcUaServer().run()
