import logging
import time

from opcua import Server

import config
from opc_tags import TAGS, VALVE_TAGS
from boiler_model import BoilerModel
from pid_controller import PIDController

logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class OPCBoilerServer:
    def __init__(self, endpoint: str = config.OPC_ENDPOINT):
        self.server = Server()
        self.server.set_endpoint(endpoint)
        self.idx = self.server.register_namespace(config.OPC_NAMESPACE_URI)

        self.nodes = {}
        self._setup_nodes()

        self.model = BoilerModel()

        self.temp_pid = PIDController(kp=0.05, ki=0.01, kd=0.02, output_min=0.0, output_max=1.0)
        self.level_pid = PIDController(kp=0.03, ki=0.005, kd=0.0, output_min=0.0, output_max=1.0)

        self._last_mode = 0.0

        self._overflow_start_time = None
        self._overflow_failsafe_active = False
        self.OVERFLOW_FAILSAFE_SECONDS = 60

    def _setup_nodes(self):
        boiler = self.server.nodes.objects.add_object(self.idx, "Boiler")
        for tag_name, props in TAGS.items():
            node = boiler.add_variable(self.idx, tag_name, props["initial"])
            if props["writable"]:
                node.set_writable()
            self.nodes[tag_name] = node
        logger.info("Создано %d тегов OPC UA", len(self.nodes))

    def _apply_manual_valves(self):
        """Режим Manual: клапаны двигает оператор через OPC-теги (слайдеры в UI)."""
        for tag_name in VALVE_TAGS:
            value = self.nodes[tag_name].get_value()
            self.model.set_valve(tag_name, value)

    def _apply_auto_control(self, dt: float):

        target_temp = self.nodes["TargetTemp"].get_value()
        target_level = self.nodes["TargetLevel"].get_value()

        measured_temp = self.model.get_measured_temperature()
        measured_level = self.model.get_measured_level_percent()

        # --- Температурный контур: доля горячей воды в суммарном притоке ---
        hot_fraction = self.temp_pid.compute(setpoint=target_temp, measured_value=measured_temp, dt=dt)

        # Суммарный приток constant = total_inflow_fraction * 2, независимо от hot_fraction.
        # 0.4 -> максимум 0.8, что заведомо меньше максимального оттока (1.0).
        total_inflow_fraction = 0.4
        self.model.set_valve("ValveHotIn", hot_fraction * total_inflow_fraction * 2)
        self.model.set_valve("ValveColdIn", (1 - hot_fraction) * total_inflow_fraction * 2)

        # --- Контур уровня: управляет сливом (ValveOut) ---
        # Работает ОДИНАКОВО что при аварии, что без неё: если уровень сильно
        # выше уставки, регулятор сам выдаст значение, близкое к максимуму —
        # никакой искусственной задержки не требуется.
        valve_out = self.level_pid.compute(setpoint=measured_level, measured_value=target_level, dt=dt)
        self.model.set_valve("ValveOut", valve_out)

        self.nodes["ValveHotIn"].set_value(round(self.model.valve_hot, 3))
        self.nodes["ValveColdIn"].set_value(round(self.model.valve_cold, 3))
        self.nodes["ValveOut"].set_value(round(self.model.valve_out, 3))

    def _check_overflow_failsafe(self):
        """
        Работает независимо от режима (и в Manual, и в Auto).
        Если авария держится дольше OVERFLOW_FAILSAFE_SECONDS — принудительно
        открывает клапан выхода на максимум, пока уровень не нормализуется.
        """
        is_overflow = self.model.last_step.get("overflow", 0.0) > 0 or self.model.get_level_percent() >= 99.5

        if not is_overflow:
            self._overflow_start_time = None
            self._overflow_failsafe_active = False
            return

        if self._overflow_start_time is None:
            self._overflow_start_time = time.time()
            logger.warning("АВАРИЯ: переполнение бака! Уровень=%.1f%%", self.model.get_level_percent())

        elapsed = time.time() - self._overflow_start_time

        if elapsed >= self.OVERFLOW_FAILSAFE_SECONDS:
            if not self._overflow_failsafe_active:
                logger.warning(
                    "Авария не снята %d секунд — принудительно открываю клапан выхода (failsafe)",
                    self.OVERFLOW_FAILSAFE_SECONDS,
                )
                self._overflow_failsafe_active = True
            self.model.set_valve("ValveOut", 1.0)
            self.nodes["ValveOut"].set_value(1.0)

    def publish_model_to_opc(self):
        self.nodes["InputTempHot"].set_value(round(self.model.temp_hot, 2))
        self.nodes["InputTempCold"].set_value(round(self.model.temp_cold, 2))
        self.nodes["OutputTemp"].set_value(round(self.model.get_measured_temperature(), 2))
        self.nodes["WaterLevel"].set_value(round(self.model.get_measured_level_percent(), 2))

        is_overflow = self.model.last_step.get("overflow", 0.0) > 0 or self.model.get_level_percent() >= 99.5
        self.nodes["Overflow"].set_value(1.0 if is_overflow else 0.0)

    def run(self):
        self.server.start()
        logger.info("OPC UA сервер запущен на %s", config.OPC_ENDPOINT)
        dt = config.MODEL_STEP_SECONDS
        try:
            while True:
                mode = self.nodes["ControlMode"].get_value()

                temp_hot = self.nodes["InputTempHot"].get_value()
                temp_cold = self.nodes["InputTempCold"].get_value()
                self.model.temp_hot = temp_hot
                self.model.temp_cold = temp_cold

                if mode >= 0.5 and self._last_mode < 0.5:
                    logger.info("Переключение в режим Auto — сброс ПИД-регуляторов")
                    self.temp_pid.reset()
                    self.level_pid.reset()
                self._last_mode = mode

                if mode >= 0.5:
                    self._apply_auto_control(dt)
                else:
                    self._apply_manual_valves()

                self._check_overflow_failsafe()

                self.model.step(dt=dt)
                self.publish_model_to_opc()
                time.sleep(dt)
        except KeyboardInterrupt:
            logger.info("Остановка сервера по Ctrl+C")
        finally:
            self.server.stop()


if __name__ == "__main__":
    server = OPCBoilerServer()
    try:
        server.run()
    except KeyboardInterrupt:
        pass