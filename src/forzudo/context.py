"""Context Engine - Enriquece recordatorios con datos reales."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forzudo.notion import WorkoutEntry


# =============================================================================
# CONFIGURACIÓN 5/3/1 BBB (copia independiente, no toca BBD Analytics)
# =============================================================================

PROGRAM_START = "2026-02-20"
BODYWEIGHT = 86.0

# Training Maxes iniciales
TRAINING_MAX = {
    "ohp": 58,
    "deadlift": 140,
    "bench": 76,
    "squat": 80,
}

# Incrementos por ciclo
TM_INCREMENT = {
    "ohp": 2,
    "deadlift": 4,
    "bench": 2,
    "squat": 4,
}

# Configuración de días
DAY_CONFIG = {
    1: {"name": "Día 1 - OHP", "main_lift": "ohp", "focus": "Press + Hombros", "color": "#f97316"},
    2: {"name": "Día 2 - Deadlift", "main_lift": "deadlift", "focus": "Peso Muerto", "color": "#ef4444"},
    3: {"name": "Día 3 - Bench", "main_lift": "bench", "focus": "Press de Banca", "color": "#3b82f6"},
    4: {"name": "Día 4 - Squat", "main_lift": "squat", "focus": "Sentadilla", "color": "#22c55e"},
}

# Estructura del ciclo (Beyond 5/3/1)
MACRO_CYCLE_LENGTH = 7  # 3 semanas + 3 semanas + 1 deload

CYCLE_WEEKS = {
    1: {"name": "Semana 5s", "sets": [
        {"pct": 0.65, "reps": 5},
        {"pct": 0.75, "reps": 5},
        {"pct": 0.85, "reps": "5+"},
    ]},
    2: {"name": "Semana 3s", "sets": [
        {"pct": 0.70, "reps": 3},
        {"pct": 0.80, "reps": 3},
        {"pct": 0.90, "reps": "3+"},
    ]},
    3: {"name": "Semana 531", "sets": [
        {"pct": 0.75, "reps": 5},
        {"pct": 0.85, "reps": 3},
        {"pct": 0.95, "reps": "1+"},
    ]},
    4: {"name": "Deload", "sets": [
        {"pct": 0.40, "reps": 5},
        {"pct": 0.50, "reps": 5},
        {"pct": 0.60, "reps": 5},
    ]},
}


# =============================================================================
# CÁLCULOS DEL CICLO
# =============================================================================


def round_to_plate(weight: float) -> float:
    """Redondea al múltiplo de 2kg más cercano (placas de 1kg)."""
    return round(weight / 2) * 2


@dataclass
class CycleState:
    """Estado actual del ciclo 5/3/1."""
    
    week_in_macro: int      # 1-7
    week_type: int          # 1=5s, 2=3s, 3=531, 4=deload
    week_name: str
    macro_num: int          # Número de macro ciclo
    tm_bumps_completed: int # Cuántos bumps de TM hemos hecho
    completed_weeks: int    # Semanas totales completadas


def get_cycle_state(total_sessions: int) -> CycleState:
    """Calcula la posición actual en el ciclo 5/3/1."""
    completed_weeks = total_sessions // 4  # 4 sesiones por semana
    macro_num = (completed_weeks // MACRO_CYCLE_LENGTH) + 1
    week_in_macro = (completed_weeks % MACRO_CYCLE_LENGTH) + 1
    
    if week_in_macro <= 3:
        week_type = week_in_macro
    elif week_in_macro <= 6:
        week_type = week_in_macro - 3
    else:
        week_type = 4  # Deload
    
    # Calcular TM bumps completados
    total_completed_blocks = 0
    for m in range(macro_num):
        if m < macro_num - 1:
            total_completed_blocks += 2
        else:
            if week_in_macro > 3:
                total_completed_blocks += 1
            if week_in_macro > 6:
                total_completed_blocks += 1
    
    return CycleState(
        week_in_macro=week_in_macro,
        week_type=week_type,
        week_name=CYCLE_WEEKS.get(week_type, {}).get("name", "?"),
        macro_num=macro_num,
        tm_bumps_completed=total_completed_blocks,
        completed_weeks=completed_weeks,
    )


def get_effective_tm(lift: str, tm_bumps: int) -> float:
    """Calcula el TM efectivo después de N bumps."""
    base = TRAINING_MAX.get(lift, 0)
    increment = TM_INCREMENT.get(lift, 2)
    return base + (increment * tm_bumps)


def get_expected_weights(lift: str, week: int, tm_bumps: int = 0) -> list[dict] | None:
    """Obtiene los pesos esperados para un ejercicio en una semana dada."""
    tm = get_effective_tm(lift, tm_bumps)
    if not tm:
        return None
    
    week_config = CYCLE_WEEKS.get(week)
    if not week_config:
        return None
    
    return [
        {
            "weight": round_to_plate(tm * s["pct"]),
            "reps": s["reps"],
            "pct": s["pct"],
        }
        for s in week_config["sets"]
    ]


def get_next_session(day_num: int, cycle_state: CycleState) -> dict:
    """Obtiene información del próximo entreno."""
    day_config = DAY_CONFIG.get(day_num, DAY_CONFIG[1])
    lift = day_config["main_lift"]
    weights = get_expected_weights(lift, cycle_state.week_type, cycle_state.tm_bumps_completed)
    
    return {
        "day_name": day_config["name"],
        "focus": day_config["focus"],
        "main_lift": lift,
        "week_name": cycle_state.week_name,
        "macro_num": cycle_state.macro_num,
        "week_in_macro": cycle_state.week_in_macro,
        "working_sets": weights or [],
    }


# =============================================================================
# CONTEXTO DE ENTRENAMIENTO
# =============================================================================


@dataclass
class WorkoutContext:
    """Contexto completo del entrenamiento."""
    
    last_workout: WorkoutEntry | None
    hours_since_last: float | None
    cycle_state: CycleState
    next_session: dict
    needs_deload: bool
    missed_workout: bool
    
    @property
    def is_deload_week(self) -> bool:
        return self.cycle_state.week_type == 4
    
    @property
    def days_until_deload(self) -> int:
        if self.cycle_state.week_in_macro >= 7:
            return 0
        return 7 - self.cycle_state.week_in_macro


def build_context(last_workout: WorkoutEntry | None = None) -> WorkoutContext:
    """Construye el contexto completo."""
    # Calcular tiempo desde último entreno
    hours_since = None
    if last_workout:
        delta = datetime.now() - last_workout.fecha
        hours_since = delta.total_seconds() / 3600
    
    # Estimar sesiones totales desde inicio del programa
    program_start = datetime.fromisoformat(PROGRAM_START)
    days_since_start = (datetime.now() - program_start).days
    estimated_sessions = (days_since_start // 7) * 4  # ~4 sesiones/semana
    
    cycle = get_cycle_state(estimated_sessions)
    
    # Determinar próximo día
    next_day = (estimated_sessions % 4) + 1
    next_sess = get_next_session(next_day, cycle)
    
    return WorkoutContext(
        last_workout=last_workout,
        hours_since_last=hours_since,
        cycle_state=cycle,
        next_session=next_sess,
        needs_deload=cycle.week_in_macro == 7,
        missed_workout=hours_since is not None and hours_since > 48,
    )


def format_context_message(context: WorkoutContext) -> str:
    """Formatea un mensaje con el contexto actual."""
    if context.last_workout is None:
        return "🆕 No tengo registro de entrenamientos recientes. ¿Empezamos?"
    
    lines = []
    
    # Header con estado
    if context.missed_workout:
        lines.append(f"⚠️ Llevas {context.hours_since_last:.0f}h sin entrenar")
    elif context.is_deload_week:
        lines.append("🧘 Semana de deload - recuperación activa")
    else:
        lines.append(f"💪 {context.cycle_state.week_name} (Macro {context.cycle_state.macro_num})")
    
    # Info del último entreno
    lines.append(f"\n📅 Último: {context.last_workout.ejercicio}")
    lines.append(f"   {context.last_workout.fecha.strftime('%d/%m/%Y')}")
    if context.last_workout.peso_top > 0:
        lines.append(f"   Top: {context.last_workout.peso_top:.0f}kg")
    
    # Próximo entreno
    if not context.is_deload_week:
        ns = context.next_session
        lines.append(f"\n🎯 Próximo: {ns['day_name']}")
        lines.append(f"   {ns['focus']}")
        
        if ns['working_sets']:
            lines.append("   Sets:")
            for i, s in enumerate(ns['working_sets'], 1):
                lines.append(f"     {i}. {s['weight']:.0f}kg × {s['reps']}")
    
    # Alertas
    if 0 < context.days_until_deload <= 3:
        lines.append(f"\n⏰ Deload en {context.days_until_deload} días")
    
    return "\n".join(lines)


def get_quick_status(last_workout: WorkoutEntry | None = None) -> str:
    """Devuelve un resumen rápido del estado."""
    ctx = build_context(last_workout)
    return format_context_message(ctx)
