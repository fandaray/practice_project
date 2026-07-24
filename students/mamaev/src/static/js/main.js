let currentValve = "";
let lastData = null;
let chartInstance = null;
let currentGraphType = null;

// История для графиков
const HISTORY_LENGTH = 60;
let history = {
    time: [],
    valve_hot: [],
    valve_cold: [],
    valve_out: [],
    water_level: [],
    output_temp: []
};

// Флаг, что уставки уже установлены при загрузке
let uiInitialized = false;

// Обновление SVG-схемы
function updateVisuals(data) {
    // Уровень воды
    const levelPercent = data.water_level;
    const maxHeight = 265;
    const waterHeight = (levelPercent / 100) * maxHeight;
    const waterRect = document.getElementById('water-level-rect');
    waterRect.setAttribute('height', waterHeight);
    waterRect.setAttribute('y', 375 - waterHeight);

    document.getElementById('level-percent-text').textContent = Math.round(levelPercent) + '%';

    // Температуры
    document.getElementById('boiler-temp-text').textContent = data.output_temp.toFixed(1) + ' °C';
    document.getElementById('input-hot-text').textContent = data.input_temp_hot.toFixed(1) + ' °C';
    document.getElementById('input-cold-text').textContent = data.input_temp_cold.toFixed(1) + ' °C';
    document.getElementById('output-temp-text').textContent = data.output_temp.toFixed(1) + ' °C';

    // Клапаны
    const valves = [
        { id: 'valve-hot-line', value: data.valve_hot },
        { id: 'valve-cold-line', value: data.valve_cold },
        { id: 'valve-out-line', value: data.valve_out }
    ];

    valves.forEach(v => {
        const line = document.getElementById(v.id);
        if (!line) return;
        const angle = (v.value / 100) * 90;
        const circleId = v.id.replace('-line', '');
        const circle = document.getElementById(circleId);
        if (!circle) return;
        const cx = parseInt(circle.getAttribute('cx'));
        const cy = parseInt(circle.getAttribute('cy'));
        line.setAttribute('transform', `rotate(${angle}, ${cx}, ${cy})`);
    });
}

// Инициализация элементов управления (ползунки, чекбокс) из данных
function initUI(data) {
    document.getElementById('setpoint-temp-slider').value = data.setpoint_temp;
    document.getElementById('setpoint-temp-display').textContent = data.setpoint_temp.toFixed(1);
    document.getElementById('setpoint-level-slider').value = data.setpoint_level;
    document.getElementById('setpoint-level-display').textContent = data.setpoint_level.toFixed(1);
    document.getElementById('auto-mode-switch').checked = data.auto_mode;
    uiInitialized = true;
}

// Запрос данных с сервера
function fetchData() {
    fetch("/data")
        .then(res => res.json())
        .then(data => {
            lastData = data;
            updateVisuals(data);

            // Если UI ещё не инициализирован, устанавливаем начальные значения
            if (!uiInitialized) {
                initUI(data);
            }

            // Добавляем в историю
            const now = new Date().toLocaleTimeString();
            history.time.push(now);
            history.valve_hot.push(data.valve_hot);
            history.valve_cold.push(data.valve_cold);
            history.valve_out.push(data.valve_out);
            history.water_level.push(data.water_level);
            history.output_temp.push(data.output_temp);

            if (history.time.length > HISTORY_LENGTH) {
                history.time.shift();
                history.valve_hot.shift();
                history.valve_cold.shift();
                history.valve_out.shift();
                history.water_level.shift();
                history.output_temp.shift();
            }

            // Обновляем график, если открыт
            if (chartInstance && currentGraphType) {
                updateChartData();
            }
        })
        .catch(err => console.error('Ошибка загрузки данных:', err));
}

// Обновление данных графика
function updateChartData() {
    if (!chartInstance || !currentGraphType) return;
    chartInstance.data.labels = history.time.slice();
    switch(currentGraphType) {
        case 'valve_hot':
            chartInstance.data.datasets[0].data = history.valve_hot.slice();
            break;
        case 'valve_cold':
            chartInstance.data.datasets[0].data = history.valve_cold.slice();
            break;
        case 'valve_out':
            chartInstance.data.datasets[0].data = history.valve_out.slice();
            break;
        case 'boiler':
            chartInstance.data.datasets[0].data = history.water_level.slice();
            if (chartInstance.data.datasets.length > 1) {
                chartInstance.data.datasets[1].data = history.output_temp.slice();
            }
            break;
        default: return;
    }
    chartInstance.update('none');
}

// Создание графика
function createGraph(type) {
    const canvas = document.getElementById('graphCanvas');
    const ctx = canvas.getContext('2d');

    if (chartInstance) {
        chartInstance.destroy();
        chartInstance = null;
    }

    let label = '', dataset = [], color = '', unit = '';
    let isBoiler = false, dataset2 = null;

    switch(type) {
        case 'valve_hot':
            label = 'Горячий клапан';
            dataset = history.valve_hot.slice();
            color = '#d32f2f';
            unit = '%';
            break;
        case 'valve_cold':
            label = 'Холодный клапан';
            dataset = history.valve_cold.slice();
            color = '#1976d2';
            unit = '%';
            break;
        case 'valve_out':
            label = 'Выходной клапан';
            dataset = history.valve_out.slice();
            color = '#2e7d32';
            unit = '%';
            break;
        case 'boiler':
            isBoiler = true;
            label = 'Бойлер';
            dataset = history.water_level.slice();
            color = '#2196F3';
            unit = '%';
            dataset2 = {
                label: 'Температура',
                data: history.output_temp.slice(),
                borderColor: '#FF5722',
                backgroundColor: 'rgba(255,87,34,0.1)',
                yAxisID: 'y1'
            };
            break;
        default: return;
    }

    const datasets = [{
        label: label + (isBoiler ? ' (уровень)' : ''),
        data: dataset,
        borderColor: color,
        backgroundColor: 'rgba(33,150,243,0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.1
    }];

    if (isBoiler && dataset2) {
        datasets.push({
            label: dataset2.label,
            data: dataset2.data,
            borderColor: dataset2.borderColor,
            backgroundColor: dataset2.backgroundColor,
            borderWidth: 2,
            fill: true,
            tension: 0.1,
            yAxisID: dataset2.yAxisID
        });
    }

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: history.time.slice(),
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            scales: {
                y: {
                    beginAtZero: true,
                    max: isBoiler ? 100 : 100,
                    title: { display: true, text: unit }
                },
                y1: {
                    position: 'right',
                    beginAtZero: true,
                    max: 100,
                    grid: { drawOnChartArea: false },
                    title: { display: true, text: '°C' }
                }
            },
            plugins: {
                legend: { labels: { font: { size: 12 } } }
            }
        }
    });

    document.getElementById('graphModalLabel').textContent = `График: ${label}`;
}

// Открыть график
function openGraph(type) {
    currentGraphType = type;
    createGraph(type);
    const modal = new bootstrap.Modal(document.getElementById('graphModal'));
    modal.show();
}

// Управление клапаном
function openValveModal(valveName) {
    currentValve = valveName;
    const modal = new bootstrap.Modal(document.getElementById('valveModal'));
    modal.show();

    let currentValue = 50;
    if (lastData) {
        const map = {
            'ValveHotIn': 'valve_hot',
            'ValveColdIn': 'valve_cold',
            'ValveOut': 'valve_out'
        };
        currentValue = lastData[map[valveName]] || 50;
    }
    document.getElementById('valveRange').value = currentValue;
    document.getElementById('valveValue').textContent = currentValue;
}

function saveValve() {
    const value = document.getElementById('valveRange').value;
    fetch("/set_valve", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: currentValve, value: value })
    })
        .then(res => res.json())
        .then(() => {
            fetchData();
            bootstrap.Modal.getInstance(document.getElementById('valveModal')).hide();
        })
        .catch(err => console.error('Ошибка установки клапана:', err));
}

document.getElementById('valveRange').addEventListener('input', function(e) {
    document.getElementById('valveValue').textContent = e.target.value;
});

// ---- Автоматика ----
function applySetpoints() {
    const temp = document.getElementById('setpoint-temp-slider').value;
    const level = document.getElementById('setpoint-level-slider').value;

    // Сначала обновляем отображение
    document.getElementById('setpoint-temp-display').textContent = parseFloat(temp).toFixed(1);
    document.getElementById('setpoint-level-display').textContent = parseFloat(level).toFixed(1);

    // Отправляем на сервер
    Promise.all([
        fetch("/set_setpoint", {
            method: "POST",
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: "SetpointTemperature", value: parseFloat(temp) })
        }),
        fetch("/set_setpoint", {
            method: "POST",
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: "SetpointLevel", value: parseFloat(level) })
        })
    ]).then(() => {
        // После успешной отправки можно обновить данные, но не перезаписываем UI
        // Просто вызовем fetchData для обновления остальных параметров
        fetchData();
    }).catch(err => console.error('Ошибка отправки уставок:', err));
}

// Чекбокс автоматики
document.getElementById('auto-mode-switch').addEventListener('change', function() {
    const mode = this.checked;
    fetch("/set_auto_mode", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: mode })
    })
        .then(res => res.json())
        .then(() => {
            // После успешной отправки не перезаписываем чекбокс
            // Но можем обновить остальные данные
            fetchData();
        })
        .catch(err => console.error('Ошибка переключения режима:', err));
});

// Обработчики
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('circle[data-valve]').forEach(circle => {
        circle.addEventListener('click', function() {
            const valveName = this.getAttribute('data-valve');
            openValveModal(valveName);
        });
    });

    fetchData();
    setInterval(fetchData, 2000);
});