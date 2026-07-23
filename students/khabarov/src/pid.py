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


class StandardController:
    def __init__(self):
        self.pid_temp = PIDController(Kp=0.04, Ki=0.002, Kd=0.1, out_min=-0.8, out_max=0.8)
        self.pid_level = PIDController(Kp=0.08, Ki=0.003, Kd=0.15, out_min=-0.8, out_max=0.8)
        self.maintenance_threshold = 5.0
        self.hold_flow = 0.40

    def compute(self, curr_temp, curr_level, target_temp, target_level, dt):
        level_out = self.pid_level.compute(target_level, curr_level, dt)
        temp_out = self.pid_temp.compute(target_temp, curr_temp, dt)

        err_temp = abs(curr_temp - target_temp)
        err_level = abs(curr_level - target_level)

        if err_temp <= self.maintenance_threshold and err_level <= self.maintenance_threshold:
            base_flow = self.hold_flow

            base_flow += level_out * 0.2
            base_flow = max(0.25, min(base_flow, 0.55))

            v_out_cmd = base_flow * 1.05

            mix = temp_out * 0.7
            v_hot_cmd = base_flow + mix + 0.03
            v_cold_cmd = base_flow - mix

        else:
            if level_out > 0:
                base_in = 0.15 + level_out * 1.1
                v_out_cmd = 0.1
            else:
                base_in = 0.12
                v_out_cmd = 0.15 + abs(level_out) * 1.3

            v_hot_cmd = base_in + temp_out * 1.2
            v_cold_cmd = base_in - temp_out * 1.2

        v_hot_cmd = max(0.0, min(v_hot_cmd, 1.0))
        v_cold_cmd = max(0.0, min(v_cold_cmd, 1.0))
        v_out_cmd = max(0.0, min(v_out_cmd, 1.0))

        return v_hot_cmd, v_cold_cmd, v_out_cmd
