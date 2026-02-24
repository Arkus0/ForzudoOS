"""Context Engine - Enriquece recordatorios con datos reales."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from forzudo.notion import (
    CycleState,
    WorkoutEntry,
    get_cycle_state,
    get_expected_weights,
    get_last_workout,
    get_next_session,
    get_workouts_last_n_hours,
)


@dataclass
class WorkoutContext:
    """Contexto completo del entrenamiento."""
    
    # Último entreno
    last_workout: WorkoutEntry | None
    hours_since_last: float | None
    
    # Estado del ciclo
    cycle_state: CycleState | None
    
    # Próximo entreno
    next_session: dict | None
    
    # Alertas
    needs_deload: bool
    missed_workout: bool
    
    @property
    def is_deload_week(self) -> bool:
        if self.cycle_state is None:
            return False
        return self.cycle_state.week_type == 4
    
    @property
    def days_until_deload(self) -> int | None:
        if self.cycle_state is None:
            return None
        if self.cycle_state.week_in_macro >= 7:
            return 0
        return 7 - self.cycle_state.week_in_macro


def build_context() -> WorkoutContext:
    """Construye el contexto completo desde Notion."""
    # Obtener último entreno
    last = get_last_workout()
    
    hours_since = None
    if last:
        delta = datetime.now() - last.date
        hours_since = delta.total_seconds() / 3600
    
    # Calcular estado del ciclo (asumiendo ~4 sesiones/semana desde el inicio)
    # Esto es una aproximación - en producción contaríamos sesiones reales
    program_start = datetime(2026, 2, 20)
    days_since_start = (datetime.now() - program_start).days
    estimated_sessions = (days_since_start // 7) * 4  # ~4 sesiones/semana
    
    cycle = get_cycle_state(estimated_sessions)
    
    # Determinar próximo día (rotación: 1→2→3→4→1)
    next_day = (estimated_sessions % 4) + 1
    next_sess = get_next_session(next_day, cycle)
    
    # Alertas
    needs_deload = cycle.week_in_macro == 7
    missed_workout = hours_since is not None and hours_since > 48
    
    return WorkoutContext(
        last_workout=last,
        hours_since_last=hours_since,
        cycle_state=cycle,
        next_session=next_sess,
        needs_deload=needs_deload,
        missed_workout=missed_workout,
    )


def format_reminder_with_context(template: str, context: WorkoutContext) -> str:
    """Formatea un mensaje de recordatorio con contexto enriquecido."""
    
    if context.last_workout is None:
        return "🆕 No tengo registro de entrenamientos recientes. ¿Empezamos?"
    
    # Mensaje base según el tipo de recordatorio
    lines = []
    
    # Header con estado
    if context.missed_workout:
        lines.append(f"⚠️ Llevas {context.hours_since_last:.0f}h sin entrenar")
    elif context.is_deload_week:
        lines.append("🧘 Semana de deload - recuperación activa")
    else:
        lines.append(f"💪 Semana {context.cycle_state.week_name if context.cycle_state else '?'}")
    
    # Info del último entreno
    if context.last_workout:
        lines.append(f"\n📅 Último: {context.last_workout.exercise} ({context.last_workout.date.strftime('%d/%m')})")
    
    # Próximo entreno
    if context.next_session and not context.is_deload_week:
        ns = context.next_session
        lines.append(f"\n🎯 Próximo: {ns['day_name']}")
        lines.append(f"   Focus: {ns['focus']}")
        
        if ns['working_sets']:
            lines.append("   Sets:")
            for i, s in enumerate(ns['working_sets'], 1):
                lines.append(f"     {i}. {s['weight']}kg x {s['reps']}")
    
    # Alertas especiales
    if context.days_until_deload is not None and 0 < context.days_until_deload <= 3:
        lines.append(f"\n⏰ Deload en {context.days_until_deload} días")
    
    return "\n".join(lines)


def get_quick_status() -> str:
    """Devuelve un resumen rápido del estado."""
    ctx = build_context()
    return format_reminder_with_context("", ctx)
