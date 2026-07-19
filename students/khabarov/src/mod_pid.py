class PID:
    """Простой ПИД-регулятор с антивиндапом."""

    def __init__(self, Kp, Ki, Kd, out_min, out_max, integral_limit=5.0):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.out_min = out_min
        self.out_max = out_max
        self.integral_limit = integral_limit
        self.integral = 0.0
        self.prev_error = 0.0

    def compute(self, setpoint, pv, dt):
        error = setpoint - pv
        self.integral += error * dt
        self.integral = max(min(self.integral, self.integral_limit), -self.integral_limit)
        derivative = (error - self.prev_error) / dt if dt > 0 else 0.0
        self.prev_error = error
        output = self.Kp * error + self.Ki * self.integral + self.Kd * derivative
        return max(min(output, self.out_max), self.out_min)


class ModifiedController:
    def __init__(self, max_valve_open=0.65, safety_open_in=0.05, safety_open_out=0.85):
        self.max_open = max_valve_open
        self.safety_in = safety_open_in
        self.safety_out = safety_open_out

        self.pid_level = PID(Kp=0.12, Ki=0.003, Kd=0.25, out_min=-0.7, out_max=0.7, integral_limit=3.5)
        self.pid_temp = PID(Kp=0.035, Ki=0.001, Kd=0.15, out_min=-0.6, out_max=0.6, integral_limit=2.5)

        self.maintenance_threshold = 4.0
        self.hold_flow = 0.38

    def reset(self):
        self.pid_level.integral = self.pid_temp.integral = 0.0
        self.pid_level.prev_error = self.pid_temp.prev_error = 0.0

    def compute(self, curr_temp, curr_level, target_temp, target_level, dt):
        if curr_level > 85.0:
            return self.safety_in, self.safety_in, self.safety_out

        err_t = abs(curr_temp - target_temp)
        err_l = abs(curr_level - target_level)
        u_level = self.pid_level.compute(target_level, curr_level, dt)
        u_temp = self.pid_temp.compute(target_temp, curr_temp, dt)

        if err_t <= self.maintenance_threshold and err_l <= self.maintenance_threshold:
            base_flow = self.hold_flow

            base_flow += u_level * 0.12
            base_flow = max(0.25, min(base_flow, 0.52))
            v_out_cmd = base_flow * 1.08

            mix = u_temp * 0.65
            v_hot_cmd = base_flow + mix
            v_cold_cmd = base_flow - mix

        else:
            if u_level > 0:
                base_in = 0.1 + u_level * 1.0
                v_out_cmd = 0.08
            else:
                base_in = 0.08
                v_out_cmd = 0.12 + abs(u_level) * 1.4

            v_hot_cmd = base_in + u_temp * 1.1
            v_cold_cmd = base_in - u_temp * 1.1

            if target_level - curr_level > 18:
                v_hot_cmd += 0.20
                v_cold_cmd += 0.20

        v_hot_cmd = max(0.0, min(v_hot_cmd, self.max_open))
        v_cold_cmd = max(0.0, min(v_cold_cmd, self.max_open))
        v_out_cmd = max(0.0, min(v_out_cmd, 1.0))

        return v_hot_cmd, v_cold_cmd, v_out_cmd
