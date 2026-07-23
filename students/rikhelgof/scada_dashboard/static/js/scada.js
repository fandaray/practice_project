const POLL_INTERVAL_MS = 1000;

// геометрия ёмкости на SVG (должна соответствовать index.html)
const TANK = { x: 270, y: 90, width: 220, height: 260 };

const els = {
  connLamp: document.getElementById("connLamp"),
  connText: document.getElementById("connText"),
  clock: document.getElementById("clock"),

  rLevel: document.getElementById("rLevel"),
  rTemp: document.getElementById("rTemp"),
  rPressure: document.getElementById("rPressure"),

  alarmHigh: document.getElementById("alarmHigh"),
  alarmLow: document.getElementById("alarmLow"),
  alarmTemp: document.getElementById("alarmTemp"),

  ilOverflow: document.getElementById("ilOverflow"),
  ilOvertemp: document.getElementById("ilOvertemp"),
  hotAutoBadge: document.getElementById("hotAutoBadge"),
  coldAutoBadge: document.getElementById("coldAutoBadge"),
  outAutoBadge: document.getElementById("outAutoBadge"),
  heaterAutoBadge: document.getElementById("heaterAutoBadge"),

  levelAutoToggle: document.getElementById("levelAutoToggle"),
  tempAutoToggle: document.getElementById("tempAutoToggle"),

  waterBody: document.getElementById("waterBody"),
  waterSurface: document.getElementById("waterSurface"),
  waterStopTop: document.getElementById("waterStopTop"),

  heaterCoil: document.getElementById("heaterCoil"),

  valveHotDisc: document.getElementById("valveHotDisc"),
  valveColdDisc: document.getElementById("valveColdDisc"),
  valveOutDisc: document.getElementById("valveOutDisc"),
  valveHotReadout: document.getElementById("valveHotReadout"),
  valveColdReadout: document.getElementById("valveColdReadout"),
  valveOutReadout: document.getElementById("valveOutReadout"),

  flowHot: document.getElementById("flowHot"),
  flowHotDown: document.getElementById("flowHotDown"),
  flowCold: document.getElementById("flowCold"),
  flowColdDown: document.getElementById("flowColdDown"),
  flowOut: document.getElementById("flowOut"),
  flowOutDown: document.getElementById("flowOutDown"),
};

const sliders = Array.from(document.querySelectorAll(".setpoint input[type='range']")).map((input) => ({
  input,
  out: document.getElementById(`${input.id}Val`),
  tag: input.dataset.tag,
  unit: input.dataset.unit || "%",
}));

// группы ручных слайдеров, которые блокируются, пока соответствующий авторегулятор включён
const inletSetpointWrappers = ["sHot", "sCold", "sOut"].map((id) =>
  document.getElementById(id).closest(".setpoint")
);
const heaterSetpointWrapper = document.getElementById("sHeat").closest(".setpoint");

let userIsDragging = false;

function tempToColor(tempC) {
  // 12°C -> синий (холодная), 75°C+ -> янтарно-красный (горячая)
  const t = Math.max(0, Math.min(1, (tempC - 15) / (85 - 15)));
  const cold = [62, 143, 196];   // #3E8FC4
  const hot = [214, 84, 42];     // тёплый терракотовый для наглядности перегрева
  const mix = cold.map((c, i) => Math.round(c + (hot[i] - c) * t));
  return `rgb(${mix.join(",")})`;
}

function setValveAngle(discEl, cx, cy, pct) {
  // 0% открытия -> диск поперёк потока (90°), 100% -> вдоль потока (0°)
  const angle = 90 - (pct / 100) * 90;
  discEl.setAttribute("transform", `rotate(${angle} ${cx} ${cy})`);
}

function setFlow(pathEl, pct) {
  const flowing = pct > 1;
  pathEl.classList.toggle("is-flowing", flowing);
  const speed = flowing ? Math.max(0.25, 1.1 - pct / 130) : 1;
  pathEl.style.animationDuration = `${speed}s`;
}

function updateClock() {
  const now = new Date();
  els.clock.textContent = now.toLocaleTimeString("ru-RU", { hour12: false });
}

function applyState(state) {
  els.connLamp.className = "lamp lamp--connected";
  els.connText.textContent = "ONLINE";

  els.rLevel.innerHTML = `${state.level.toFixed(1)} <small>%</small>`;
  if (state.temperature_valid === false) {
    els.rTemp.innerHTML = `N/A <small>нет воды</small>`;
  } else {
    els.rTemp.innerHTML = `${state.temperature.toFixed(1)} <small>°C</small>`;
  }
  els.rPressure.innerHTML = `${state.pressure.toFixed(2)} <small>bar</small>`;

  els.alarmHigh.classList.toggle("is-active", !!state.level_high_alarm);
  els.alarmLow.classList.toggle("is-active", !!state.level_low_alarm);
  els.alarmTemp.classList.toggle("is-active", !!state.overtemp_alarm);

  els.ilOverflow.classList.toggle("is-active", !!state.interlock_overflow);
  els.ilOvertemp.classList.toggle("is-active", !!state.interlock_overtemp);

  const levelAuto = !!state.level_auto;
  const tempAuto = !!state.temperature_auto;

  els.hotAutoBadge.classList.toggle("is-active", !!state.interlock_overflow || levelAuto);
  els.coldAutoBadge.classList.toggle("is-active", !!state.interlock_overflow || levelAuto);
  els.outAutoBadge.classList.toggle("is-active", levelAuto);
  els.heaterAutoBadge.classList.toggle("is-active", !!state.interlock_overtemp || tempAuto);

  // переключатели авторегуляторов + блокировка соответствующих ручных слайдеров
  els.levelAutoToggle.checked = levelAuto;
  els.tempAutoToggle.checked = tempAuto;
  inletSetpointWrappers.forEach((el) => el.classList.toggle("is-disabled", levelAuto));
  heaterSetpointWrapper.classList.toggle("is-disabled", tempAuto);

  // --- уровень воды в баке ---
  const levelFrac = Math.max(0, Math.min(1, state.level / 100));
  const waterHeight = TANK.height * levelFrac;
  const waterY = TANK.y + (TANK.height - waterHeight);
  els.waterBody.setAttribute("y", waterY.toFixed(1));
  els.waterBody.setAttribute("height", waterHeight.toFixed(1));
  els.waterSurface.setAttribute("transform", `translate(0, ${waterY.toFixed(1)})`);

  const color = tempToColor(state.temperature);
  els.waterStopTop.setAttribute("stop-color", color);

  // --- фактические (effective) положения - то, что РЕАЛЬНО происходит с
  //     клапанами притока и нагревателем после наложения блокировок; могут
  //     отличаться от уставки оператора (slider), если сработал interlock ---
  const hotActual = state.hot_valve_effective ?? state.hot_valve;
  const coldActual = state.cold_valve_effective ?? state.cold_valve;
  const heaterActual = state.heater_effective ?? state.heater;

  // --- нагреватель ---
  els.heaterCoil.classList.toggle("is-active", heaterActual > 1);

  // --- клапаны: угол + подписи + анимация потока в трубах (по факту, не по уставке) ---
  setValveAngle(els.valveHotDisc, 170, 70, hotActual);
  setValveAngle(els.valveColdDisc, 550, 70, coldActual);
  setValveAngle(els.valveOutDisc, 380, 410, state.outlet_valve);

  els.valveHotReadout.textContent = `${Math.round(hotActual)}%`;
  els.valveColdReadout.textContent = `${Math.round(coldActual)}%`;
  els.valveOutReadout.textContent = `${Math.round(state.outlet_valve)}%`;

  els.valveHotDisc.classList.toggle("is-overridden", !!state.interlock_overflow);
  els.valveColdDisc.classList.toggle("is-overridden", !!state.interlock_overflow);

  setFlow(els.flowHot, hotActual);
  setFlow(els.flowHotDown, hotActual);
  setFlow(els.flowCold, coldActual);
  setFlow(els.flowColdDown, coldActual);
  setFlow(els.flowOut, state.outlet_valve);
  setFlow(els.flowOutDown, state.outlet_valve);

  // --- синхронизация слайдеров (если пользователь их сейчас не тянет) ---
  if (!userIsDragging) {
    for (const { input, out, tag, unit } of sliders) {
      if (document.activeElement !== input) {
        const value = state[tag] ?? 0;
        input.value = value;
        out.textContent = `${Math.round(value)}${unit}`;
      }
    }
  }
}

function setDisconnected() {
  els.connLamp.className = "lamp lamp--disconnected";
  els.connText.textContent = "OFFLINE";
}

async function pollState() {
  try {
    const res = await fetch("/api/state");
    if (!res.ok) throw new Error("bad status");
    const state = await res.json();
    if (!state.connected) throw new Error("not connected");
    applyState(state);
  } catch (err) {
    setDisconnected();
  }
}

let debounceTimers = {};
function sendSetpoint(tag, value) {
  clearTimeout(debounceTimers[tag]);
  debounceTimers[tag] = setTimeout(() => {
    fetch("/api/setpoint", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tag, value }),
    }).catch(() => setDisconnected());
  }, 120);
}

sliders.forEach(({ input, out, tag, unit }) => {
  input.addEventListener("pointerdown", () => (userIsDragging = true));
  input.addEventListener("pointerup", () => (userIsDragging = false));
  input.addEventListener("input", () => {
    out.textContent = `${input.value}${unit}`;
    sendSetpoint(tag, Number(input.value));
  });
});

els.levelAutoToggle.addEventListener("change", () => {
  sendSetpoint("level_auto", els.levelAutoToggle.checked);
});
els.tempAutoToggle.addEventListener("change", () => {
  sendSetpoint("temperature_auto", els.tempAutoToggle.checked);
});

updateClock();
setInterval(updateClock, 1000);
pollState();
setInterval(pollState, POLL_INTERVAL_MS);
