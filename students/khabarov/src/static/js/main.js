let currentValve = "";
let previousAutoMode = false;

function updateData() {
    fetch('/data')
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                console.error("Ошибка:", data.error);
                return;
            }

            document.getElementById("input-hot").textContent = Number(data.input_temp_hot).toFixed(1);
            document.getElementById("input-cold").textContent = Number(data.input_temp_cold).toFixed(1);
            document.getElementById("output-temp").textContent = Number(data.output_temp).toFixed(1);
            document.getElementById("water-level").textContent = Number(data.water_level).toFixed(1);
            document.getElementById("valve-hot").textContent = Number(data.valve_hot).toFixed(1);
            document.getElementById("valve-cold").textContent = Number(data.valve_cold).toFixed(1);
            document.getElementById("valve-out").textContent = Number(data.valve_out).toFixed(1);

            const manualButtons = [
                document.getElementById('btn-valve-hot'),
                document.getElementById('btn-valve-cold'),
                document.getElementById('btn-valve-out')
            ];
            const statusIndicator = document.getElementById('status-indicator');

            if (data.auto_mode) {
                manualButtons.forEach(btn => btn.style.display = 'none');  
                if (data.target_temp !== undefined && data.target_level !== undefined) {
                    const tempError = Math.abs(data.output_temp - data.target_temp);
                    const levelError = Math.abs(data.water_level - data.target_level);

                    if (data.targets_reached) {
                        statusIndicator.innerHTML = `Мы достигли нужных значений! (Т: ${data.target_temp.toFixed(1)}°C, Ур: ${data.target_level.toFixed(1)}%)`;
                        statusIndicator.style.background = "#d4edda";
                        statusIndicator.style.color = "#155724";
                    } else {
                        statusIndicator.innerHTML = `ТАУ в работе... (Осталось: ΔT=${tempError.toFixed(1)}°C, ΔУр=${levelError.toFixed(1)}%)<br><small>Ручной режим заблокирован</small>`;
                        statusIndicator.style.background = '#ffeeba';
                        statusIndicator.style.color = "#856404";
                    }
                } else {
                    statusIndicator.innerHTML = `ТАУ в работе...<br><small>Ручной режим заблокирован</small>`;
                    statusIndicator.style.background = '#ffeeba';
                }
            } else {
                manualButtons.forEach(btn => btn.style.display = 'inline-block');
                statusIndicator.innerText = 'Дистанционное управление / Ожидание уставки ТАУ';
                statusIndicator.style.background = '#eee';
                statusIndicator.style.color = "#383d41";
            }

            if (previousAutoMode === true && data.auto_mode === false) {
                alert('ТАУ завершило работу (уставки достигнуты). Ручной режим разблокирован.');
            }

            previousAutoMode = data.auto_mode;
        })
        .catch(err => console.error("Ошибка сети:", err));
}

function openValveModal(valveName) {
    currentValve = valveName;
    new bootstrap.Modal(document.getElementById("valveModal")).show();
}

function saveValve() {
    const value = document.getElementById("valveRange").value;
    fetch("/set_valve", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: currentValve, value: value })
    }).then(() => {
        bootstrap.Modal.getInstance(document.getElementById("valveModal")).hide();
    });
}

function applyAutoSettings() {
    const targetTemp = document.getElementById("target-temp").value;
    const targetLevel = document.getElementById("target-level").value;
    fetch("/set_auto", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_temp: parseFloat(targetTemp), target_level: parseFloat(targetLevel) })
    });
}

function openSettingsModal() {
    new bootstrap.Modal(document.getElementById("settingsModal")).show();
}

function applyDynamicsSettings() {
    const inTime = document.getElementById("valve-in-time").value;
    const outTime = document.getElementById("valve-out-time").value;
    
    fetch("/set_dynamics", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            valve_in_time: parseFloat(inTime), 
            valve_out_time: parseFloat(outTime) 
        })
    })
    .then(res => {
        if (!res.ok) throw new Error("HTTP " + res.status); // Ловим 404 и 500
        return res.json();
    })
    .then(data => {
        if (data.status === "ok") {
            alert("Настройки динамики сохранены!");
            bootstrap.Modal.getInstance(document.getElementById("settingsModal")).hide();
        } else {
            alert("Ошибка сервера: " + (data.error || "Неизвестная ошибка"));
        }
    })
    .catch(err => {
        alert("Ошибка соединения с сервером: " + err.message);
        console.error("Сетевая ошибка:", err);
    });
}
function validateAndSetAuto() {
    const tempInput = document.getElementById("target-temp").value;
    const levelInput = document.getElementById("target-level").value;
    
    const temp = parseFloat(tempInput);
    const level = parseFloat(levelInput);

    if (isNaN(temp) || temp < 0 || temp > 100 || isNaN(level) || level < 0 || level > 100) {
        alert("Ошибка: Значения температуры и уровня должны быть числами от 0 до 100.");
        return; 
    }

    fetch("/set_auto", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_temp: temp, target_level: level })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "ok") {
            alert("Настройки ТАУ успешно применены!");
        } else {
            alert("Ошибка сервера: " + (data.error || "Неизвестная ошибка"));
        }
    })
    .catch(err => {
        alert("Ошибка соединения: " + err.message);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const valveRange = document.getElementById('valveRange');
    const valveValue = document.getElementById('valveValue');
    if (valveRange && valveValue) {
        valveRange.addEventListener('input', (e) => { valveValue.innerText = e.target.value; });
    }
    
    setInterval(updateData, 1000);
});