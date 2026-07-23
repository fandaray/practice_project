"""
Физическая модель бойлера (баллона смешения).

Идея: ёмкость с двумя входными потоками (горячая и холодная вода)
и одним выходным потоком. Открытие каждого клапана задаётся в процентах
(0-100). Модель на каждом шаге симуляции считает:

  1. Баланс массы  -> изменение уровня воды в ёмкости.
  2. Баланс энергии -> изменение температуры смеси.
  3. Давление       -> упрощённая зависимость от температуры и уровня.

Всё выражено в "инженерных" единицах: уровень в %, температура в °C,
давление в барах, расход клапана - в % открытия, который линейно
пересчитывается в объёмный расход (л/с) через Cv (пропускную способность).
"""

from dataclasses import dataclass


@dataclass
class BoilerParameters:
    tank_area_m2: float = 0.3          # площадь сечения ёмкости, м^2 (компактный бак ~300 л)
    tank_height_m: float = 1.0         # высота ёмкости, м
    hot_supply_temp_c: float = 75.0    # температура горячей магистрали
    cold_supply_temp_c: float = 12.0   # температура холодной магистрали
    ambient_temp_c: float = 20.0       # температура окружающей среды
    heat_loss_kw_per_degree: float = 0.05  # теплопотери через стенки, кВт на 1°C разницы с окружением
    valve_cv_hot: float = 2.5           # л/с при 100% открытия
    valve_cv_cold: float = 3.0
    valve_cv_outlet: float = 4.0
    heater_max_kw: float = 1000.0      # мощность нагревателя (увеличена для наглядной демонстрации -
                                         # перегрев на 100% мощности наступает примерно за 30-35 секунд)


@dataclass
class BoilerState:
    level_pct: float = 45.0
    temperature_c: float = 40.0
    pressure_bar: float = 1.2
    hot_valve_pct: float = 0.0
    cold_valve_pct: float = 0.0
    outlet_valve_pct: float = 0.0
    heater_pct: float = 0.0

    level_high_alarm: bool = False
    level_low_alarm: bool = False
    overtemp_alarm: bool = False

    # --- технологические блокировки (interlocks) ---
    # срабатывают поверх уставок оператора и защищают оборудование
    interlock_overflow: bool = False   # авто-закрытие притока при переполнении
    interlock_overtemp: bool = False   # авто-отключение нагревателя при перегреве

    # фактическое (после наложения блокировок) состояние исполнительных механизмов -
    # то, что физически происходит с клапанами/нагревателем, в отличие от команды оператора
    hot_valve_effective_pct: float = 0.0
    cold_valve_effective_pct: float = 0.0
    heater_effective_pct: float = 0.0

    # достоверно ли текущее показание температуры - False, если в баке физически
    # нет воды и не идёт приток (сенсору буквально нечего измерять)
    temperature_valid: bool = True

    # --- автоматическое регулирование (термостат по температуре, регулятор уровня) ---
    # пока включено, регулятор сам считает нужные положения клапанов/нагревателя,
    # переписывая *_pct поверх того, что было задано вручную
    level_auto_enabled: bool = False
    level_setpoint_pct: float = 50.0
    temperature_auto_enabled: bool = False
    temperature_setpoint_c: float = 60.0


class BoilerModel:
    """Считает эволюцию состояния бойлера во времени."""

    # --- аварийная сигнализация (просто предупреждает оператора) ---
    LEVEL_HIGH_ALARM = 92.0
    LEVEL_LOW_ALARM = 8.0
    OVERTEMP_ALARM = 90.0

    # --- пороги технологических блокировок (действуют автоматически, с гистерезисом,
    #     чтобы не "дребезжать" туда-обратно на границе срабатывания) ---
    OVERFLOW_TRIP = 96.0          # закрыть приток при достижении
    OVERFLOW_TRIP_RESET = 90.0    # разблокировать приток, когда уровень опустится ниже

    OVERTEMP_TRIP = 95.0          # отключить нагреватель при достижении
    OVERTEMP_TRIP_RESET = 88.0    # разрешить нагрев снова, когда температура упадёт ниже

    # --- параметры автоматических регуляторов (простое пропорциональное управление) ---
    LEVEL_DEADBAND_PCT = 1.5      # зона нечувствительности - внутри неё регулятор ничего не делает
    LEVEL_KP = 10.0                # %открытия клапана на 1% отклонения уровня от уставки
    TEMP_DEADBAND_C = 1.0         # зона нечувствительности по температуре, °C
    TEMP_KP = 20.0                 # %мощности нагревателя на 1°C отклонения от уставки

    WATER_SPECIFIC_HEAT_KJ = 4.186  # кДж / (кг * °C)
    WATER_DENSITY_KG_L = 1.0

    def __init__(self, params: BoilerParameters = None, state: BoilerState = None):
        self.params = params or BoilerParameters()
        self.state = state or BoilerState()

    # --- управляющие воздействия -------------------------------------------------
    def set_hot_valve(self, pct: float):
        self.state.hot_valve_pct = _clamp(pct, 0, 100)

    def set_cold_valve(self, pct: float):
        self.state.cold_valve_pct = _clamp(pct, 0, 100)

    def set_outlet_valve(self, pct: float):
        self.state.outlet_valve_pct = _clamp(pct, 0, 100)

    def set_heater(self, pct: float):
        self.state.heater_pct = _clamp(pct, 0, 100)

    def set_level_setpoint(self, pct: float):
        self.state.level_setpoint_pct = _clamp(pct, 0, 100)

    def set_level_auto(self, enabled: bool):
        self.state.level_auto_enabled = bool(enabled)

    def set_temperature_setpoint(self, temp_c: float):
        # верхний предел = порог блокировки перегрева: нет смысла разрешать
        # ставить цель, которую регулятор не сможет достичь без срабатывания защиты
        self.state.temperature_setpoint_c = _clamp(temp_c, 10.0, self.OVERTEMP_TRIP)

    def set_temperature_auto(self, enabled: bool):
        self.state.temperature_auto_enabled = bool(enabled)

    # --- расчёт одного шага --------------------------------------------------
    def step(self, dt_s: float):
        p, s = self.params, self.state

        # --- автоматическое регулирование: если включено, регулятор сам считает
        #     нужные положения клапанов/нагревателя вместо ручных значений оператора.
        #     Считается ДО блокировок, поэтому защита от переполнения/перегрева
        #     точно так же может переопределить решение регулятора. ---
        if s.level_auto_enabled:
            error = s.level_setpoint_pct - s.level_pct
            if abs(error) <= self.LEVEL_DEADBAND_PCT:
                s.hot_valve_pct = 0.0
                s.cold_valve_pct = 0.0
                s.outlet_valve_pct = 0.0
            elif error > 0:
                # уровень ниже уставки - доливаем горячей и холодной поровну
                demand = _clamp(error * self.LEVEL_KP, 0.0, 100.0)
                s.hot_valve_pct = demand
                s.cold_valve_pct = demand
                s.outlet_valve_pct = 0.0
            else:
                # уровень выше уставки - сливаем излишек
                demand = _clamp(-error * self.LEVEL_KP, 0.0, 100.0)
                s.hot_valve_pct = 0.0
                s.cold_valve_pct = 0.0
                s.outlet_valve_pct = demand

        if s.temperature_auto_enabled:
            error = s.temperature_setpoint_c - s.temperature_c
            if error <= self.TEMP_DEADBAND_C:
                s.heater_pct = 0.0
            else:
                s.heater_pct = _clamp(error * self.TEMP_KP, 0.0, 100.0)

        # --- технологические блокировки: считаются от состояния на конец предыдущего
        #     шага и определяют, что РЕАЛЬНО происходит с исполнительными механизмами
        #     в этом шаге, независимо от того, что задал оператор ---
        if not s.interlock_overflow and s.level_pct >= self.OVERFLOW_TRIP:
            s.interlock_overflow = True
        elif s.interlock_overflow and s.level_pct <= self.OVERFLOW_TRIP_RESET:
            s.interlock_overflow = False

        if not s.interlock_overtemp and s.temperature_c >= self.OVERTEMP_TRIP:
            s.interlock_overtemp = True
        elif s.interlock_overtemp and s.temperature_c <= self.OVERTEMP_TRIP_RESET:
            s.interlock_overtemp = False

        # эффективные (фактические) положения - клапаны притока принудительно
        # закрыты при переполнении, нагреватель принудительно выключен при перегреве
        s.hot_valve_effective_pct = 0.0 if s.interlock_overflow else s.hot_valve_pct
        s.cold_valve_effective_pct = 0.0 if s.interlock_overflow else s.cold_valve_pct
        s.heater_effective_pct = 0.0 if s.interlock_overtemp else s.heater_pct

        tank_volume_l = p.tank_area_m2 * p.tank_height_m * 1000.0
        current_volume_l = tank_volume_l * (s.level_pct / 100.0)

        hot_flow_l_s = p.valve_cv_hot * (s.hot_valve_effective_pct / 100.0)
        cold_flow_l_s = p.valve_cv_cold * (s.cold_valve_effective_pct / 100.0)
        outlet_flow_l_s = p.valve_cv_outlet * (s.outlet_valve_pct / 100.0)

        # если ёмкость почти пуста - на выходе физически нечему течь
        if current_volume_l <= 0.01:
            outlet_flow_l_s = 0.0

        net_flow_l_s = hot_flow_l_s + cold_flow_l_s - outlet_flow_l_s
        new_volume_l = max(0.0, current_volume_l + net_flow_l_s * dt_s)
        new_volume_l = min(new_volume_l, tank_volume_l)

        # --- энергетический баланс (упрощённо, вода как в идеальном смесителе) --
        mass_now_kg = current_volume_l * self.WATER_DENSITY_KG_L
        energy_now_kj = mass_now_kg * self.WATER_SPECIFIC_HEAT_KJ * s.temperature_c

        hot_mass_kg = hot_flow_l_s * dt_s * self.WATER_DENSITY_KG_L
        cold_mass_kg = cold_flow_l_s * dt_s * self.WATER_DENSITY_KG_L
        outlet_mass_kg = outlet_flow_l_s * dt_s * self.WATER_DENSITY_KG_L

        energy_in_kj = (
            hot_mass_kg * self.WATER_SPECIFIC_HEAT_KJ * p.hot_supply_temp_c
            + cold_mass_kg * self.WATER_SPECIFIC_HEAT_KJ * p.cold_supply_temp_c
        )
        energy_out_kj = outlet_mass_kg * self.WATER_SPECIFIC_HEAT_KJ * s.temperature_c

        heater_energy_kj = p.heater_max_kw * (s.heater_effective_pct / 100.0) * dt_s
        # теплопотери идут через стенки бака в окружающую среду - зависят от разницы
        # температур, а не от массы воды внутри (иначе больший бак остывал бы быстрее,
        # что физически неверно)
        loss_energy_kj = p.heat_loss_kw_per_degree * (s.temperature_c - p.ambient_temp_c) * dt_s

        new_mass_kg = mass_now_kg + hot_mass_kg + cold_mass_kg - outlet_mass_kg
        new_mass_kg = max(0.0, min(new_mass_kg, tank_volume_l * self.WATER_DENSITY_KG_L))

        # при почти пустом баке (меньше ~1 литра) энергобаланс "энергия / масса"
        # становится численно неустойчивым: любая мелочь (нагреватель, теплопотери)
        # делится на исчезающе малую массу и даёт нефизичный скачок температуры.
        # В этом случае просто берём температуру притока (или не меняем её, если
        # притока нет) - нагревать/охлаждать по факту нечего.
        MIN_MASS_KG = 1.0
        if new_mass_kg < MIN_MASS_KG:
            total_inflow_l_s = hot_flow_l_s + cold_flow_l_s
            if total_inflow_l_s > 0:
                new_temperature_c = (
                    hot_flow_l_s * p.hot_supply_temp_c + cold_flow_l_s * p.cold_supply_temp_c
                ) / total_inflow_l_s
                s.temperature_valid = True
            else:
                new_temperature_c = s.temperature_c
                s.temperature_valid = False
        else:
            new_energy_kj = energy_now_kj + energy_in_kj - energy_out_kj + heater_energy_kj - loss_energy_kj
            new_temperature_c = new_energy_kj / (new_mass_kg * self.WATER_SPECIFIC_HEAT_KJ)
            s.temperature_valid = True

        # --- давление: базовое + вклад от нагрева и заполнения ---------------
        fill_ratio = new_volume_l / tank_volume_l if tank_volume_l else 0.0
        new_pressure_bar = (
            1.0
            + 0.35 * fill_ratio
            + max(0.0, (new_temperature_c - 60.0)) * 0.02
        )

        # --- запись нового состояния ------------------------------------------
        s.level_pct = (new_volume_l / tank_volume_l) * 100.0 if tank_volume_l else 0.0
        s.temperature_c = _clamp(new_temperature_c, 0.0, 130.0)
        s.pressure_bar = round(new_pressure_bar, 3)

        s.level_high_alarm = s.level_pct >= self.LEVEL_HIGH_ALARM
        s.level_low_alarm = s.level_pct <= self.LEVEL_LOW_ALARM
        s.overtemp_alarm = s.temperature_c >= self.OVERTEMP_ALARM

        return s


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
