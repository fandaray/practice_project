class BoilerModel:
    def __init__(self, max_volume=100.0, temp_cold=10.0, temp_hot=90.0):
        self.max_volume = max_volume
        self.temp_cold = temp_cold
        self.temp_hot = temp_hot

        # Начальные физические условия
        self.volume = 0.0
        self.temp = temp_cold  # Начальная температура воды равна температуре холодной на входе

        # Физическое положение клапанов (от 0.0 до 1.0)
        self.valve_hot = 0.5
        self.valve_cold = 0.5
        self.valve_out = 1.0

        # Командное (заданное контроллером или оператором) положение клапанов
        self.valve_hot_cmd = 0.5
        self.valve_cold_cmd = 0.5
        self.valve_out_cmd = 1.0

        # Время полного хода клапанов (из настроек интерфейса)
        self.valve_in_time = 60.0
        self.valve_out_time = 60.0

        # Словарь для хранения текущих скоростей движения клапанов (нужно для S-кривой)
        self.valve_vel = {
            'valve_hot': 0.0,
            'valve_cold': 0.0,
            'valve_out': 0.0
        }

    def _simulate_valve_dynamics(self, dt):
        for attr in ['valve_hot', 'valve_cold', 'valve_out']:
            cmd = getattr(self, attr + '_cmd')
            curr = getattr(self, attr)
            travel_time = self.valve_in_time if 'out' not in attr else self.valve_out_time
            speed = dt / max(travel_time, 0.1)

            # Если ошибка меньше порога – сразу ставим точно
            if abs(cmd - curr) < 1e-6:
                setattr(self, attr, cmd)
                continue

            if curr < cmd:
                setattr(self, attr, min(curr + speed, cmd))
            elif curr > cmd:
                setattr(self, attr, max(curr - speed, cmd))
    def _calc_flow(self, valve_fraction, travel_time):
        """
        Линейный расчет расхода воды.
        При открытии клапана на 100% (valve_fraction = 1.0) весь объем бойлера (max_volume)
        вытекает/натекает ровно за время travel_time.
        """
        return (self.max_volume / max(travel_time, 0.1)) * valve_fraction

    def step(self, dt=1.0):
        # 1. Сначала рассчитываем плавное перемещение клапанов
        self._simulate_valve_dynamics(dt)

        # 2. Считаем объемы втекающей и вытекающей воды за шаг времени dt
        in_hot = self._calc_flow(self.valve_hot, self.valve_in_time) * dt
        in_cold = self._calc_flow(self.valve_cold, self.valve_in_time) * dt
        out = self._calc_flow(self.valve_out, self.valve_out_time) * dt

        old_volume = self.volume
        incoming = in_hot + in_cold
        total_mass = old_volume + incoming

        # 3. Расчет теплового баланса (смешивание температур)
        if total_mass > 0 and incoming > 0:
            mixed_temp = (in_hot * self.temp_hot + in_cold * self.temp_cold) / incoming
            self.temp = (self.temp * old_volume + mixed_temp * incoming) / total_mass

        # 4. Обновление текущего уровня (объема) воды с ограничением от 0 до max_volume
        self.volume = max(0.0, min(old_volume + incoming - out, self.max_volume))

    def get_level_percent(self):
        return (self.volume / self.max_volume) * 100.0

    def get_temperature(self):
        return self.temp