/**
 * ForzudoOS Dashboard - App Logic
 * 
 * Este dashboard lee datos desde archivos JSON estáticos generados
 * por el backend de ForzudoOS. No requiere servidor.
 */

// Configuración del programa 5/3/1
const CONFIG = {
    programStart: '2026-02-20',
    bodyweight: 86,
    trainingMax: {
        ohp: 58,
        deadlift: 140,
        bench: 76,
        squat: 80,
    },
    tmIncrement: {
        ohp: 2,
        deadlift: 4,
        bench: 2,
        squat: 4,
    },
    dayConfig: {
        1: { name: 'Día 1 - OHP', lift: 'ohp', focus: 'Press + Hombros', color: '#f97316' },
        2: { name: 'Día 2 - Deadlift', lift: 'deadlift', focus: 'Peso Muerto', color: '#ef4444' },
        3: { name: 'Día 3 - Bench', lift: 'bench', focus: 'Press de Banca', color: '#3b82f6' },
        4: { name: 'Día 4 - Squat', lift: 'squat', focus: 'Sentadilla', color: '#22c55e' },
    },
    cycleWeeks: {
        1: { name: 'Semana 5s', sets: [
            { pct: 0.65, reps: 5 },
            { pct: 0.75, reps: 5 },
            { pct: 0.85, reps: '5+' },
        ]},
        2: { name: 'Semana 3s', sets: [
            { pct: 0.70, reps: 3 },
            { pct: 0.80, reps: 3 },
            { pct: 0.90, reps: '3+' },
        ]},
        3: { name: 'Semana 531', sets: [
            { pct: 0.75, reps: 5 },
            { pct: 0.85, reps: 3 },
            { pct: 0.95, reps: '1+' },
        ]},
        4: { name: 'Deload', sets: [
            { pct: 0.40, reps: 5 },
            { pct: 0.50, reps: 5 },
            { pct: 0.60, reps: 5 },
        ]},
    },
    macroCycleLength: 7,
};

// Estado de la aplicación
let appState = {
    workouts: [],
    lastWorkout: null,
    cycleState: null,
    nextSession: null,
};

// Utilidades
function roundToPlate(weight) {
    return Math.round(weight / 2) * 2;
}

function getEffectiveTM(lift, tmBumps) {
    const base = CONFIG.trainingMax[lift] || 0;
    const increment = CONFIG.tmIncrement[lift] || 2;
    return base + (increment * tmBumps);
}

function getCycleState(totalSessions) {
    const completedWeeks = Math.floor(totalSessions / 4);
    const macroNum = Math.floor(completedWeeks / CONFIG.macroCycleLength) + 1;
    const weekInMacro = (completedWeeks % CONFIG.macroCycleLength) + 1;
    
    let weekType, miniCycle;
    if (weekInMacro <= 3) {
        weekType = weekInMacro;
        miniCycle = 1;
    } else if (weekInMacro <= 6) {
        weekType = weekInMacro - 3;
        miniCycle = 2;
    } else {
        weekType = 4;
        miniCycle = null;
    }
    
    let totalCompletedBlocks = 0;
    for (let m = 0; m < macroNum; m++) {
        if (m < macroNum - 1) {
            totalCompletedBlocks += 2;
        } else {
            if (weekInMacro > 3) totalCompletedBlocks += 1;
            if (weekInMacro > 6) totalCompletedBlocks += 1;
        }
    }
    
    return {
        weekInMacro,
        weekType,
        weekName: CONFIG.cycleWeeks[weekType]?.name || '?',
        macroNum,
        tmBumpsCompleted: totalCompletedBlocks,
        completedWeeks,
    };
}

function getExpectedWeights(lift, week, tmBumps) {
    const tm = getEffectiveTM(lift, tmBumps);
    if (!tm) return null;
    
    const weekConfig = CONFIG.cycleWeeks[week];
    if (!weekConfig) return null;
    
    return weekConfig.sets.map(s => ({
        weight: roundToPlate(tm * s.pct),
        reps: s.reps,
        pct: s.pct,
    }));
}

function getNextSession(dayNum, cycleState) {
    const dayConfig = CONFIG.dayConfig[dayNum] || CONFIG.dayConfig[1];
    const lift = dayConfig.lift;
    const weights = getExpectedWeights(lift, cycleState.weekType, cycleState.tmBumpsCompleted);
    
    return {
        dayName: dayConfig.name,
        focus: dayConfig.focus,
        mainLift: lift,
        weekName: cycleState.weekName,
        macroNum: cycleState.macroNum,
        weekInMacro: cycleState.weekInMacro,
        workingSets: weights || [],
    };
}

// Cargar datos
async function loadData() {
    try {
        // Intentar cargar desde data.json (generado por el backend)
        const response = await fetch('data.json');
        if (response.ok) {
            const data = await response.json();
            appState.workouts = data.workouts || [];
        }
    } catch (e) {
        console.log('No data.json found, using mock data');
        // Datos de ejemplo para desarrollo
        appState.workouts = [
            {
                ejercicio: 'OHP (Barbell)',
                fecha: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
                diaBbb: 'Día 1 - OHP',
                semana: 1,
                pesoTop: 50,
                reps: '5/5/8',
                volumen: 2500,
            },
        ];
    }
    
    // Calcular estado
    calculateState();
}

function calculateState() {
    // Último entreno
    if (appState.workouts.length > 0) {
        appState.workouts.sort((a, b) => new Date(b.fecha) - new Date(a.fecha));
        appState.lastWorkout = appState.workouts[0];
    }
    
    // Estado del ciclo
    const programStart = new Date(CONFIG.programStart);
    const now = new Date();
    const daysSinceStart = Math.floor((now - programStart) / (1000 * 60 * 60 * 24));
    const estimatedSessions = Math.floor(daysSinceStart / 7) * 4;
    
    appState.cycleState = getCycleState(estimatedSessions);
    
    // Próximo entreno
    const nextDay = (estimatedSessions % 4) + 1;
    appState.nextSession = getNextSession(nextDay, appState.cycleState);
}

// Renderizar UI
function renderDateTime() {
    const now = new Date();
    const timeEl = document.querySelector('.datetime .time');
    const dateEl = document.querySelector('.datetime .date');
    
    timeEl.textContent = now.toLocaleTimeString('es-ES', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    dateEl.textContent = now.toLocaleDateString('es-ES', { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    });
}

function renderCycle() {
    const { cycleState } = appState;
    if (!cycleState) return;
    
    document.getElementById('cycle-badge').textContent = cycleState.weekName;
    document.getElementById('macro-num').textContent = cycleState.macroNum;
    document.getElementById('week-name').textContent = cycleState.weekName;
    document.getElementById('week-position').textContent = `${cycleState.weekInMacro}/7`;
    
    // Progress bar
    const progress = (cycleState.weekInMacro / CONFIG.macroCycleLength) * 100;
    document.getElementById('cycle-progress').style.width = `${progress}%`;
}

function renderNextWorkout() {
    const { nextSession } = appState;
    if (!nextSession) return;
    
    document.getElementById('workout-day').textContent = `Macro ${nextSession.macroNum}`;
    document.getElementById('workout-name').textContent = nextSession.dayName;
    document.getElementById('workout-focus').textContent = nextSession.focus;
    
    const setsList = document.getElementById('sets-list');
    setsList.innerHTML = '';
    
    nextSession.workingSets.forEach((set, i) => {
        const setEl = document.createElement('div');
        setEl.className = 'set-item';
        setEl.innerHTML = `
            <span class="set-number">${i + 1}</span>
            <span class="set-weight">${set.weight} kg</span>
            <span class="set-reps">× ${set.reps}</span>
        `;
        setsList.appendChild(setEl);
    });
}

function renderLastWorkout() {
    const { lastWorkout } = appState;
    
    if (!lastWorkout) {
        document.getElementById('last-exercise').textContent = 'Sin entrenos registrados';
        return;
    }
    
    const fecha = new Date(lastWorkout.fecha);
    const now = new Date();
    const hoursAgo = Math.floor((now - fecha) / (1000 * 60 * 60));
    
    document.getElementById('last-date').textContent = fecha.toLocaleDateString('es-ES');
    document.getElementById('last-exercise').textContent = lastWorkout.ejercicio;
    document.getElementById('last-weight').textContent = lastWorkout.pesoTop || '-';
    document.getElementById('last-hours').textContent = hoursAgo;
}

function renderAlerts() {
    const alertsList = document.getElementById('alerts-list');
    alertsList.innerHTML = '';
    
    const { cycleState, lastWorkout } = appState;
    const alerts = [];
    
    // Alerta de deload próximo
    if (cycleState && cycleState.weekInMacro >= 5) {
        const daysUntil = 7 - cycleState.weekInMacro;
        alerts.push({
            type: 'warning',
            icon: '⏰',
            text: `Deload en ${daysUntil} días`,
        });
    }
    
    // Alerta de no entreno
    if (lastWorkout) {
        const hoursAgo = Math.floor((new Date() - new Date(lastWorkout.fecha)) / (1000 * 60 * 60));
        if (hoursAgo > 48) {
            alerts.push({
                type: 'error',
                icon: '⚠️',
                text: `Llevas ${hoursAgo}h sin entrenar`,
            });
        }
    }
    
    // Alerta de deload actual
    if (cycleState && cycleState.weekType === 4) {
        alerts.push({
            type: 'success',
            icon: '🧘',
            text: 'Semana de deload - recupera bien',
        });
    }
    
    if (alerts.length === 0) {
        alerts.push({
            type: 'success',
            icon: '✅',
            text: 'Todo en orden, forzudo',
        });
    }
    
    alerts.forEach(alert => {
        const alertEl = document.createElement('div');
        alertEl.className = `alert alert-${alert.type}`;
        alertEl.innerHTML = `
            <span class="alert-icon">${alert.icon}</span>
            <span class="alert-text">${alert.text}</span>
        `;
        alertsList.appendChild(alertEl);
    });
}

function renderCalendar() {
    const calendarGrid = document.getElementById('calendar-grid');
    calendarGrid.innerHTML = '';
    
    const now = new Date();
    const startOfWeek = new Date(now);
    startOfWeek.setDate(now.getDate() - now.getDay() + 1); // Lunes
    
    const dayNames = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];
    const workoutDays = [1, 2, 3, 4]; // Días de entreno (L-J)
    
    for (let i = 0; i < 7; i++) {
        const date = new Date(startOfWeek);
        date.setDate(startOfWeek.getDate() + i);
        
        const isToday = date.toDateString() === now.toDateString();
        const isWorkoutDay = workoutDays.includes(i + 1);
        const dayNum = i + 1;
        
        const dayEl = document.createElement('div');
        dayEl.className = `calendar-day ${isToday ? 'today' : ''} ${isWorkoutDay ? 'workout' : ''}`;
        dayEl.innerHTML = `
            <span class="calendar-day-name">${dayNames[i]}</span>
            <span class="calendar-day-number">${date.getDate()}</span>
            ${isWorkoutDay ? `<span class="calendar-day-workout">${CONFIG.dayConfig[dayNum]?.lift?.toUpperCase() || ''}</span>` : ''}
        `;
        
        calendarGrid.appendChild(dayEl);
    }
}

function renderStats() {
    const { workouts, cycleState } = appState;
    
    // Sesiones totales (estimadas)
    const programStart = new Date(CONFIG.programStart);
    const daysSince = Math.floor((new Date() - programStart) / (1000 * 60 * 60 * 24));
    const estimatedSessions = Math.floor(daysSince / 7) * 4;
    
    // Volumen total
    const totalVolume = workouts.reduce((sum, w) => sum + (w.volumen || 0), 0);
    
    // TM promedio
    const currentTM = cycleState ? getEffectiveTM('bench', cycleState.tmBumpsCompleted) : 0;
    
    // Streak (días consecutivos con entreno)
    let streak = 0;
    if (workouts.length > 0) {
        // Simplificado: contar días desde el último entreno
        const lastDate = new Date(workouts[0].fecha);
        const daysSinceLast = Math.floor((new Date() - lastDate) / (1000 * 60 * 60 * 24));
        streak = daysSinceLast < 2 ? Math.max(1, 7 - daysSinceLast) : 0;
    }
    
    document.getElementById('stat-sessions').textContent = estimatedSessions;
    document.getElementById('stat-volume').textContent = totalVolume > 0 ? Math.floor(totalVolume / 1000) + 'k' : '-';
    document.getElementById('stat-streak').textContent = streak || '-';
    document.getElementById('stat-tm').textContent = currentTM || '-';
}

// Inicialización
async function init() {
    await loadData();
    
    renderDateTime();
    renderCycle();
    renderNextWorkout();
    renderLastWorkout();
    renderAlerts();
    renderCalendar();
    renderStats();
    
    // Actualizar cada minuto
    setInterval(() => {
        renderDateTime();
    }, 60000);
}

// Iniciar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', init);
