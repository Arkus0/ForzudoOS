"""Cliente Notion para ForzudoOS - adaptado de BBD Analytics."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import requests

# Configuración
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_531_LOGBOOK_DB = os.environ.get(
    "NOTION_531_LOGBOOK_DB", "31e7df96-6afb-4b58-a34c-817cb2bf887d"
)

# Rate limit: 3 req/s
RATE_LIMIT_DELAY = 0.35
BASE_URL = "https://api.notion.com/v1"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _post(endpoint: str, body: dict) -> dict:
    time.sleep(RATE_LIMIT_DELAY)
    r = requests.post(f"{BASE_URL}{endpoint}", headers=_headers(), json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def query_database(database_id: str, filter_obj: dict | None = None) -> list[dict]:
    """Query una base de datos de Notion."""
    body: dict[str, Any] = {"page_size": 100}
    if filter_obj:
        body["filter"] = filter_obj

    all_results = []
    has_more = True
    start_cursor = None

    while has_more:
        if start_cursor:
            body["start_cursor"] = start_cursor
        data = _post(f"/databases/{database_id}/query", body)
        all_results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return all_results


@dataclass
class WorkoutEntry:
    """Entrada de entrenamiento simplificada."""
    
    exercise: str
    date: datetime
    day_name: str
    week: int
    n_sets: int
    reps_str: str
    top_set: str
    hevy_id: str


def get_recent_workouts(days: int = 30) -> list[WorkoutEntry]:
    """Obtiene entrenamientos recientes."""
    since = datetime.now() - timedelta(days=days)
    
    filter_obj = {
        "property": "Fecha",
        "date": {"on_or_after": since.strftime("%Y-%m-%d")},
    }
    
    pages = query_database(NOTION_531_LOGBOOK_DB, filter_obj)
    
    workouts = []
    for p in pages:
        props = p.get("properties", {})
        
        def get_text(prop_name: str) -> str:
            rt = props.get(prop_name, {}).get("rich_text", [])
            return rt[0].get("plain_text", "") if rt else ""
        
        def get_title(prop_name: str) -> str:
            t = props.get(prop_name, {}).get("title", [])
            return t[0].get("plain_text", "") if t else ""
        
        date_str = props.get("Fecha", {}).get("date", {}).get("start", "")
        
        workouts.append(WorkoutEntry(
            exercise=get_title("Ejercicio"),
            date=datetime.fromisoformat(date_str) if date_str else datetime.now(),
            day_name=props.get("Día", {}).get("select", {}).get("name", ""),
            week=props.get("Semana", {}).get("number", 0),
            n_sets=props.get("Series", {}).get("number", 0),
            reps_str=get_text("Reps"),
            top_set=get_text("Top Set"),
            hevy_id=get_text("Hevy ID"),
        ))
    
    return sorted(workouts, key=lambda w: w.date, reverse=True)


def get_last_workout() -> WorkoutEntry | None:
    """Obtiene el último entrenamiento registrado."""
    workouts = get_recent_workouts(days=7)
    return workouts[0] if workouts else None


def get_workouts_last_n_hours(hours: int) -> list[WorkoutEntry]:
    """Obtiene entrenamientos de las últimas N horas."""
    since = datetime.now() - timedelta(hours=hours)
    workouts = get_recent_workouts(days=max(1, hours // 24 + 1))
    return [w for w in workouts if w.date >= since]


@dataclass
class CycleState:
    """Estado actual del ciclo 5/3/1."""
    
    week_in_macro: int
    week_type: int  # 1=5s, 2=3s, 3=531, 4=deload
    week_name: str
    macro_num: int
    tm_bumps_completed: int
    completed_weeks: int


# Configuración del programa 5/3/1 (copiada de bbd-analytics)
MACRO_CYCLE_LENGTH = 7
PROGRAM_START = "2026-02-20"

TRAINING_MAX = {
    "ohp": 58,
    "deadlift": 140,
    "bench": 76,
    "squat": 80,
}

TM_INCREMENT = {
    "ohp": 2,
    "deadlift": 4,
    "bench": 2,
    "squat": 4,
}

DAY_CONFIG = {
    1: {"name": "BBB Día 1 - OHP", "main_lift": "ohp", "focus": "Press + Hombros"},
    2: {"name": "BBB Día 2 - Deadlift", "main_lift": "deadlift", "focus": "Peso Muerto"},
    3: {"name": "BBB Día 3 - Bench", "main_lift": "bench", "focus": "Press de Banca"},
    4: {"name": "BBB Día 4 - Zercher", "main_lift": "squat", "focus": "Sentadilla Zercher"},
}

CYCLE_WEEKS = {
    1: {"name": "Semana 5s", "sets": [{"pct": 0.65, "reps": 5}, {"pct": 0.75, "reps": 5}, {"pct": 0.85, "reps": "5+"}]},
    2: {"name": "Semana 3s", "sets": [{"pct": 0.70, "reps": 3}, {"pct": 0.80, "reps": 3}, {"pct": 0.90, "reps": "3+"}]},
    3: {"name": "Semana 531", "sets": [{"pct": 0.75, "reps": 5}, {"pct": 0.85, "reps": 3}, {"pct": 0.95, "reps": "1+"}]},
    4: {"name": "Deload", "sets": [{"pct": 0.40, "reps": 5}, {"pct": 0.50, "reps": 5}, {"pct": 0.60, "reps": 5}]},
}


def get_cycle_state(total_sessions: int) -> CycleState:
    """Calcula la posición actual en el ciclo 5/3/1."""
    completed_weeks = total_sessions // 4
    macro_num = (completed_weeks // MACRO_CYCLE_LENGTH) + 1
    week_in_macro = (completed_weeks % MACRO_CYCLE_LENGTH) + 1

    if week_in_macro <= 3:
        week_type = week_in_macro
        mini_cycle = 1
    elif week_in_macro <= 6:
        week_type = week_in_macro - 3
        mini_cycle = 2
    else:
        week_type = 4
        mini_cycle = None

    # Calcular TM bumps
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
    
    result = []
    for s in week_config["sets"]:
        weight = round(tm * s["pct"] / 2) * 2  # redondear a 2kg
        result.append({
            "weight": weight,
            "reps": s["reps"],
            "pct": s["pct"],
        })
    return result


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
        "working_sets": weights,
    }
