TAGS = {
    "InputTempHot":  {"initial": 90.0, "writable": True, "unit": "°C", "min": 0,   "max": 100, "group": "temperature"},
    "InputTempCold": {"initial": 10.0, "writable": True, "unit": "°C", "min": 0,   "max": 100, "group": "temperature"},
    "OutputTemp":    {"initial": 25.0, "writable": False, "unit": "°C", "min": 0,   "max": 120, "group": "temperature"},
    "WaterLevel":    {"initial": 0.0,  "writable": False, "unit": "%",  "min": 0,   "max": 100, "group": "level"},

    "ValveHotIn":    {"initial": 0.5,  "writable": True,  "unit": "",   "min": 0.0, "max": 1.0, "group": "valve"},
    "ValveColdIn":   {"initial": 0.5,  "writable": True,  "unit": "",   "min": 0.0, "max": 1.0, "group": "valve"},
    "ValveOut":      {"initial": 1.0,  "writable": True,  "unit": "",   "min": 0.0, "max": 1.0, "group": "valve"},

    "ControlMode":   {"initial": 0.0,  "writable": True,  "unit": "",   "min": 0.0, "max": 1.0, "group": "control"},
    "TargetTemp":    {"initial": 50.0, "writable": True,  "unit": "°C", "min": 10.0, "max": 90.0, "group": "control"},
    "TargetLevel":   {"initial": 60.0, "writable": True,  "unit": "%",  "min": 0.0,  "max": 100.0, "group": "control"},

    "Overflow":      {"initial": 0.0,  "writable": False, "unit": "",   "min": 0.0, "max": 1.0, "group": "alarm"},
}

WRITABLE_TAGS = {name for name, props in TAGS.items() if props["writable"]}

VALVE_TAGS = {name for name, props in TAGS.items() if props["writable"] and props["group"] == "valve"}


def validate_value(name: str, value: float) -> float:
    if name not in TAGS:
        raise KeyError(f"Неизвестный тег: {name}")
    props = TAGS[name]
    if not props["writable"]:
        raise ValueError(f"Тег {name} доступен только для чтения")
    return max(props["min"], min(props["max"], float(value)))