import random


class BoilerModel:
    def __init__(self):
        self.temp_hot = 90.0
        self.temp_cold = 10.0
        self.temp_out = 25.0
        self.water_volume = 0.0
        self.max_volume = 100.0

        self.valve_hot = 0.5
        self.valve_cold = 0.5
        self.valve_out = 1.0

        self.last_step = {"overflow": 0.0}
        self._noise_enabled = True

    def set_valve(self, name, value):
        if name == "ValveHotIn":
            self.valve_hot = max(0.0, min(1.0, value))
        elif name == "ValveColdIn":
            self.valve_cold = max(0.0, min(1.0, value))
        elif name == "ValveOut":
            self.valve_out = max(0.0, min(1.0, value))

    def get_level_percent(self):
        return (self.water_volume / self.max_volume) * 100.0

    def get_measured_level_percent(self):
        level = self.get_level_percent()
        if self._noise_enabled:
            noise = random.uniform(-0.5, 0.5)
            level = max(0.0, min(100.0, level + noise))
        return level

    def get_measured_temperature(self):
        if self._noise_enabled:
            noise = random.uniform(-0.3, 0.3)
            return max(0.0, self.temp_out + noise)
        return self.temp_out

    def step(self, dt=1.0):
        inflow_hot = self.valve_hot * 10.0 * dt
        inflow_cold = self.valve_cold * 10.0 * dt
        outflow = self.valve_out * 25.0 * dt

        total_inflow = inflow_hot + inflow_cold

        if total_inflow > 0:
            mixed_temp = (inflow_hot * self.temp_hot + inflow_cold * self.temp_cold) / total_inflow
        else:
            mixed_temp = self.temp_out

        new_volume = self.water_volume + total_inflow - outflow

        if new_volume > self.max_volume:
            overflow = new_volume - self.max_volume
            new_volume = self.max_volume
            self.last_step["overflow"] = overflow
        else:
            self.last_step["overflow"] = 0.0

        if new_volume < 0:
            new_volume = 0

        if new_volume > 0:
            if total_inflow > 0:
                self.temp_out = (self.temp_out * self.water_volume + mixed_temp * total_inflow) / (
                            self.water_volume + total_inflow)

            if outflow > 0:
                heat_loss = (self.temp_out - self.temp_cold) * (outflow / (self.water_volume + 1)) * dt * 0.1
                self.temp_out = max(self.temp_cold, self.temp_out - heat_loss)

        self.water_volume = new_volume