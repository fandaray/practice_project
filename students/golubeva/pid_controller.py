
class PIDController:
    def __init__(self, kp: float, ki: float, kd: float,
                 output_min: float = 0.0, output_max: float = 1.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max

        self._integral = 0.0
        self._prev_error = None

    def reset(self):
        """Сбрасывает накопленный интеграл и память о предыдущей ошибке."""
        self._integral = 0.0
        self._prev_error = None

    def compute(self, setpoint: float, measured_value: float, dt: float) -> float:
        error = setpoint - measured_value

        # Пропорциональная составляющая
        p_term = self.kp * error

        # Интегральная составляющая (с anti-windup, см. ниже)
        self._integral += error * dt
        i_term = self.ki * self._integral

        # Дифференциальная составляющая (реакция на скорость изменения ошибки)
        if self._prev_error is None:
            d_term = 0.0
        else:
            d_term = self.kd * (error - self._prev_error) / dt if dt > 0 else 0.0
        self._prev_error = error

        raw_output = p_term + i_term + d_term
        clamped_output = max(self.output_min, min(self.output_max, raw_output))

        # Anti-windup: если выход обрезался (насыщение клапана) — откатываем
        # последнее приращение интеграла, чтобы он не продолжал расти впустую.
        if clamped_output != raw_output:
            self._integral -= error * dt

        return clamped_output
