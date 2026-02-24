"""Dashboard Data Generator - Genera data.json para el dashboard."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from forzudo.context import build_context, get_cycle_state, get_next_session
from forzudo.notion import get_last_workout


def generate_dashboard_data(output_path: str = "docs/data.json") -> dict:
    """Genera el archivo de datos para el dashboard.
    
    Este archivo es leído por el dashboard estático (GitHub Pages).
    Se debe regenerar periódicamente (vía cron) para mantener actualizado.
    """
    # Intentar obtener datos reales de Notion
    workouts = []
    last_workout = None
    
    try:
        workouts_db = os.environ.get("FORZUDO_WORKOUTS_DB")
        if workouts_db:
            from forzudo.notion import get_recent_workouts
            workouts = [
                {
                    "ejercicio": w.ejercicio,
                    "fecha": w.fecha.isoformat(),
                    "diaBbb": w.dia_bbb,
                    "semana": w.semana,
                    "pesoTop": w.peso_top,
                    "reps": w.reps,
                    "volumen": w.volumen,
                    "hevyId": w.hevy_id,
                }
                for w in get_recent_workouts(workouts_db, days=30)
            ]
            last_workout = workouts[0] if workouts else None
    except Exception as e:
        print(f"⚠️ No se pudieron cargar datos de Notion: {e}")
    
    # Calcular estado del ciclo
    ctx = build_context()
    
    # Generar próximos entrenos de la semana
    upcoming = []
    today = datetime.now()
    
    for i in range(7):
        date = today + timedelta(days=i)
        day_of_week = date.weekday()  # 0=Lunes, 6=Domingo
        
        # Días de entreno: Lunes(0), Martes(1), Miércoles(2), Jueves(3)
        if day_of_week < 4:
            day_num = day_of_week + 1
            session = get_next_session(day_num, ctx.cycle_state)
            
            upcoming.append({
                "date": date.strftime("%Y-%m-%d"),
                "dayName": session["day_name"],
                "focus": session["focus"],
                "mainLift": session["main_lift"],
                "weekName": session["week_name"],
                "workingSets": session["working_sets"],
            })
    
    # Construir estructura de datos
    data = {
        "generatedAt": datetime.now().isoformat(),
        "cycle": {
            "weekInMacro": ctx.cycle_state.week_in_macro,
            "weekType": ctx.cycle_state.week_type,
            "weekName": ctx.cycle_state.week_name,
            "macroNum": ctx.cycle_state.macro_num,
            "tmBumpsCompleted": ctx.cycle_state.tm_bumps_completed,
            "completedWeeks": ctx.cycle_state.completed_weeks,
            "isDeloadWeek": ctx.is_deload_week,
            "daysUntilDeload": ctx.days_until_deload,
        },
        "nextSession": {
            "dayName": ctx.next_session["day_name"],
            "focus": ctx.next_session["focus"],
            "mainLift": ctx.next_session["main_lift"],
            "weekName": ctx.next_session["week_name"],
            "macroNum": ctx.next_session["macro_num"],
            "weekInMacro": ctx.next_session["week_in_macro"],
            "workingSets": ctx.next_session["working_sets"],
        } if ctx.next_session else None,
        "lastWorkout": last_workout,
        "workouts": workouts,
        "upcoming": upcoming,
        "alerts": generate_alerts(ctx),
        "stats": {
            "totalSessions": ctx.cycle_state.completed_weeks * 4,
            "totalVolume": sum(w.get("volumen", 0) for w in workouts),
            "currentStreak": calculate_streak(workouts),
        },
    }
    
    # Guardar archivo
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output, "w") as f:
        json.dump(data, f, indent=2, default=str)
    
    return data


def generate_alerts(ctx) -> list[dict]:
    """Genera lista de alertas basadas en el contexto."""
    alerts = []
    
    # Deload próximo
    if ctx.days_until_deload is not None and ctx.days_until_deload <= 3:
        alerts.append({
            "type": "warning",
            "icon": "⏰",
            "message": f"Deload en {ctx.days_until_deload} días",
        })
    
    # No entreno
    if ctx.missed_workout:
        alerts.append({
            "type": "error",
            "icon": "⚠️",
            "message": f"Llevas {ctx.hours_since_last:.0f}h sin entrenar",
        })
    
    # Deload actual
    if ctx.is_deload_week:
        alerts.append({
            "type": "success",
            "icon": "🧘",
            "message": "Semana de deload - recupera bien",
        })
    
    if not alerts:
        alerts.append({
            "type": "success",
            "icon": "✅",
            "message": "Todo en orden, forzudo",
        })
    
    return alerts


def calculate_streak(workouts: list[dict]) -> int:
    """Calcula el streak actual de entrenos."""
    if not workouts:
        return 0
    
    # Ordenar por fecha
    sorted_workouts = sorted(workouts, key=lambda w: w.get("fecha", ""), reverse=True)
    
    # Verificar si el último entreno fue hoy o ayer
    last_date = datetime.fromisoformat(sorted_workouts[0]["fecha"].replace("Z", "+00:00"))
    days_since = (datetime.now() - last_date).days
    
    if days_since > 1:
        return 0
    
    # Contar días consecutivos (simplificado)
    return min(len(sorted_workouts), 7)


def cmd_generate_dashboard(args: list[str]) -> int:
    """Comando CLI para generar datos del dashboard."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generar datos para dashboard")
    parser.add_argument("--output", default="dashboard/data.json", help="Ruta de salida")
    pargs = parser.parse_args(args)
    
    try:
        data = generate_dashboard_data(pargs.output)
        print(f"✅ Datos generados: {pargs.output}")
        print(f"   Ciclo: {data['cycle']['weekName']} (Macro {data['cycle']['macroNum']})")
        print(f"   Entrenos: {len(data['workouts'])}")
        print(f"   Alertas: {len(data['alerts'])}")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(cmd_generate_dashboard(sys.argv[1:]))
