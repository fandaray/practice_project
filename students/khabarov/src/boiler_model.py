class PIDController:
    def __init__(self, Kp, Ki, Kd, out_min, out_max):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.out_min = out_min
        self.out_max = out_max
        self.integral = 0.0
        self.prev_error = 0.0

    def compute(self, setpoint, pv, dt):
        error = setpoint - pv
        self.integral += error * dt
        self.integral = max(min(self.integral, 5.0), -5.0)
        derivative = (error - self.prev_error) / dt if dt > 0 else 0.0
        self.prev_error = error
        output = self.Kp * error + self.Ki * self.integral + self.Kd * derivative
        return max(min(output, self.out_max), self.out_min)


class BoilerModel:
    def __init__(self, max_volume=100.0, temp_cold=10.0, temp_hot=90.0, max_flow=2.0):
        self.max_volume = max_volume
        self.temp_cold = temp_cold
        self.temp_hot = temp_hot
        self.max_flow = max_flow
        self.volume = 0.0
        self.temp = temp_cold
        self.valve_hot, self.valve_cold, self.valve_out = 0.0, 0.0, 0.0
        self.valve_hot_cmd, self.valve_cold_cmd, self.valve_out_cmd = 0.0, 0.0, 0.0
        self.valve_in_time, self.valve_out_time = 60.0, 60.0
        self.auto_mode = False
        self.target_temp, self.target_level = 50.0, 50.0
        self.pid_temp = PIDController(Kp=0.3, Ki=0.01, Kd=0.1, out_min=-1.0, out_max=1.0)
        self.pid_level = PIDController(Kp=0.25, Ki=0.005, Kd=0.2, out_min=-1.0, out_max=1.0)

    def set_targets(self, temp, level):

        self.target_temp = max(0.0, min(float(temp), 100.0))
        self.target_level = max(0.0, min(float(level), 100.0))
        self.auto_mode = True

    def disable_auto(self):
        self.auto_mode = False
        self.valve_hot_cmd = 0.0
        self.valve_cold_cmd = 0.0
        self.valve_out_cmd = 0.0

    def _auto_control(self, dt):
        current_temp = self.get_temperature()
        current_level = self.get_level_percent()
        error_level = self.target_level - current_level

        if current_level < 15.0:
            mode = 'FILL_ONLY'
        elif abs(error_level) > 5.0:
            mode = 'FILL' if error_level > 0 else 'DRAIN'
        else:
            mode = 'STABLE'

        if mode == 'FILL_ONLY':
            self.valve_hot_cmd = 0.8
            self.valve_cold_cmd = 0.8
            self.valve_out_cmd = 0.0

        elif mode == 'FILL':
            fill_speed = min(abs(error_level) / 20.0, 0.5)
            self.valve_hot_cmd = 0.5 * fill_speed
            self.valve_cold_cmd = 0.5 * fill_speed
            self.valve_out_cmd = 0.05

        elif mode == 'DRAIN':
            self.valve_hot_cmd = 0.0
            self.valve_cold_cmd = 0.0
            self.valve_out_cmd = 0.9

        elif mode == 'STABLE':
            adjustment = error_level * 0.05
            self.valve_hot_cmd = max(0.0, min(0.2 + adjustment, 0.4))
            self.valve_cold_cmd = max(0.0, min(0.2 - adjustment, 0.4))
            self.valve_out_cmd = 0.1

        if current_level > 5.0:
            temp_err = self.target_temp - current_temp
            correction = temp_err * 0.02
            self.valve_hot_cmd = max(0.0, min(self.valve_hot_cmd + correction, 1.0))
            self.valve_cold_cmd = max(0.0, min(self.valve_cold_cmd - correction, 1.0))

    def _simulate_valve_dynamics(self, dt):
        for attr in ['valve_hot', 'valve_cold', 'valve_out']:
            cmd = getattr(self, attr + '_cmd')
            curr = getattr(self, attr)
            travel_time = self.valve_in_time if 'out' not in attr else self.valve_out_time
            speed = dt / max(travel_time, 0.1)
            if curr < cmd:
                setattr(self, attr, min(curr + speed, cmd))
            elif curr > cmd:
                setattr(self, attr, max(curr - speed, cmd))

    def step(self, dt=1.0):
        if self.auto_mode: self._auto_control(dt)
        self._simulate_valve_dynamics(dt)
        in_hot = self.valve_hot * self.max_flow * dt
        in_cold = self.valve_cold * self.max_flow * dt
        out = self.valve_out * self.max_flow * dt
        incoming = in_hot + in_cold
        if (self.volume + incoming) > 0:
            self.temp = (self.volume * self.temp + incoming * (
                        (in_hot * self.temp_hot + in_cold * self.temp_cold) / (incoming + 1e-6))) / (
                                    self.volume + incoming + 1e-6)
        self.volume = max(0.0, min(self.volume + incoming - out, self.max_volume))

    def get_temperature(self):
        return self.temp

    def get_level_percent(self):
        return (self.volume / self.max_volume) * 100