"""Cliente Notion para ForzudoOS - independiente de BBD Analytics."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import requests

# Configuración - IDs propios de ForzudoOS (no tocar BBD)
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")

# Base de datos de recordatorios (a crear)
FORZUDO_REMINDERS_DB = os.environ.get(
    "FORZUDO_REMINDERS_DB", ""  # Se creará si no existe
)

# Página padre donde crear las dbs
FORZUDO_PARENT_PAGE = os.environ.get(
    "FORZUDO_PARENT_PAGE", ""  # ID de página padre en Notion
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


def _get(endpoint: str) -> dict:
    """GET request a Notion API."""
    time.sleep(RATE_LIMIT_DELAY)
    r = requests.get(f"{BASE_URL}{endpoint}", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def _post(endpoint: str, body: dict | None = None) -> dict:
    """POST request a Notion API."""
    time.sleep(RATE_LIMIT_DELAY)
    r = requests.post(
        f"{BASE_URL}{endpoint}",
        headers=_headers(),
        json=body or {},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _patch(endpoint: str, body: dict) -> dict:
    """PATCH request a Notion API."""
    time.sleep(RATE_LIMIT_DELAY)
    r = requests.patch(
        f"{BASE_URL}{endpoint}",
        headers=_headers(),
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# =============================================================================
# GESTIÓN DE BASES DE DATOS
# =============================================================================


def create_reminders_database(parent_page_id: str | None = None) -> str:
    """Crea la base de datos de recordatorios de ForzudoOS.
    
    No interfere con BBD Analytics. Database independiente.
    """
    parent = parent_page_id or FORZUDO_PARENT_PAGE
    if not parent:
        raise ValueError("Se necesita FORZUDO_PARENT_PAGE o parent_page_id")
    
    body = {
        "parent": {"page_id": parent},
        "title": [{"type": "text", "text": {"content": "🦍 ForzudoOS - Recordatorios"}}],
        "properties": {
            "Nombre": {"title": {}},
            "Tipo": {
                "select": {
                    "options": [
                        {"name": "condicional", "color": "blue"},
                        {"name": "temporal", "color": "green"},
                        {"name": "recurrente", "color": "yellow"},
                        {"name": "evento", "color": "purple"},
                    ]
                }
            },
            "Estado": {
                "select": {
                    "options": [
                        {"name": "activo", "color": "green"},
                        {"name": "pausado", "color": "yellow"},
                        {"name": "disparado", "color": "orange"},
                        {"name": "completado", "color": "gray"},
                    ]
                }
            },
            "Condición": {"rich_text": {}},  # JSON con la condición
            "Último Check": {"date": {}},
            "Contador": {"number": {}},
            "User ID": {"rich_text": {}},
        },
    }
    
    result = _post("/databases", body)
    return result["id"]


def create_workouts_database(parent_page_id: str | None = None) -> str:
    """Crea base de datos de entrenos sincronizados (copia local, no toca Hevy).
    
    Los entrenos se sincronizan desde BBD Analytics vía webhook/manual,
    pero esta es una base de datos INDEPENDIENTE para ForzudoOS.
    """
    parent = parent_page_id or FORZUDO_PARENT_PAGE
    if not parent:
        raise ValueError("Se necesita FORZUDO_PARENT_PAGE o parent_page_id")
    
    body = {
        "parent": {"page_id": parent},
        "title": [{"type": "text", "text": {"content": "🦍 ForzudoOS - Entrenos"}}],
        "properties": {
            "Ejercicio": {"title": {}},
            "Fecha": {"date": {}},
            "Día BBB": {"select": {"options": [
                {"name": "Día 1 - OHP", "color": "orange"},
                {"name": "Día 2 - Deadlift", "color": "red"},
                {"name": "Día 3 - Bench", "color": "blue"},
                {"name": "Día 4 - Squat", "color": "green"},
            ]}},
            "Semana": {"number": {}},
            "Peso Top": {"number": {}},
            "Reps": {"rich_text": {}},
            "Volumen": {"number": {}},
            "Hevy ID": {"rich_text": {}},  # Referencia, no vinculación
            "Sincronizado": {"checkbox": {}},
        },
    }
    
    result = _post("/databases", body)
    return result["id"]


# =============================================================================
# OPERACIONES CON RECORDATORIOS
# =============================================================================


@dataclass
class ReminderEntry:
    """Entrada de recordatorio en Notion."""
    
    id: str
    nombre: str
    tipo: str
    estado: str
    condicion: dict
    ultimo_check: datetime | None
    contador: int
    user_id: str


def query_reminders(
    database_id: str,
    estado: str | None = None,
    tipo: str | None = None,
) -> list[ReminderEntry]:
    """Consulta recordatorios con filtros opcionales."""
    body: dict[str, Any] = {"page_size": 100}
    
    filters = []
    if estado:
        filters.append({"property": "Estado", "select": {"equals": estado}})
    if tipo:
        filters.append({"property": "Tipo", "select": {"equals": tipo}})
    
    if len(filters) == 1:
        body["filter"] = filters[0]
    elif len(filters) > 1:
        body["filter"] = {"and": filters}
    
    results = []
    has_more = True
    start_cursor = None
    
    while has_more:
        if start_cursor:
            body["start_cursor"] = start_cursor
        
        data = _post(f"/databases/{database_id}/query", body)
        
        for page in data.get("results", []):
            props = page.get("properties", {})
            
            def get_title(prop: str) -> str:
                t = props.get(prop, {}).get("title", [])
                return t[0].get("plain_text", "") if t else ""
            
            def get_select(prop: str) -> str:
                return props.get(prop, {}).get("select", {}).get("name", "")
            
            def get_text(prop: str) -> str:
                rt = props.get(prop, {}).get("rich_text", [])
                return rt[0].get("plain_text", "") if rt else ""
            
            date_str = props.get("Último Check", {}).get("date", {}).get("start")
            
            import json
            try:
                condicion = json.loads(get_text("Condición"))
            except json.JSONDecodeError:
                condicion = {}
            
            results.append(ReminderEntry(
                id=page["id"],
                nombre=get_title("Nombre"),
                tipo=get_select("Tipo"),
                estado=get_select("Estado"),
                condicion=condicion,
                ultimo_check=datetime.fromisoformat(date_str) if date_str else None,
                contador=props.get("Contador", {}).get("number", 0) or 0,
                user_id=get_text("User ID"),
            ))
        
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    
    return results


def create_reminder(
    database_id: str,
    nombre: str,
    tipo: str,
    condicion: dict,
    user_id: str = "juan",
) -> str:
    """Crea un nuevo recordatorio en Notion."""
    import json
    
    body = {
        "parent": {"database_id": database_id},
        "properties": {
            "Nombre": {"title": [{"text": {"content": nombre}}]},
            "Tipo": {"select": {"name": tipo}},
            "Estado": {"select": {"name": "activo"}},
            "Condición": {"rich_text": [{"text": {"content": json.dumps(condicion)}}]},
            "Contador": {"number": 0},
            "User ID": {"rich_text": [{"text": {"content": user_id}}]},
        },
    }
    
    result = _post("/pages", body)
    return result["id"]


def update_reminder_status(
    page_id: str,
    estado: str,
    increment_counter: bool = False,
) -> None:
    """Actualiza el estado de un recordatorio."""
    body = {
        "properties": {
            "Estado": {"select": {"name": estado}},
            "Último Check": {"date": {"start": datetime.now().isoformat()}},
        },
    }
    
    if increment_counter:
        # Necesitamos leer el valor actual primero
        page = _get(f"/pages/{page_id}")
        current = page["properties"].get("Contador", {}).get("number", 0) or 0
        body["properties"]["Contador"] = {"number": current + 1}
    
    _patch(f"/pages/{page_id}", body)


# =============================================================================
# SINCRONIZACIÓN DE ENTRENOS (desde BBD, sin tocarlo)
# =============================================================================


@dataclass
class WorkoutEntry:
    """Entrada de entrenamiento."""
    
    ejercicio: str
    fecha: datetime
    dia_bbb: str
    semana: int
    peso_top: float
    reps: str
    volumen: float
    hevy_id: str


def create_workout_entry(database_id: str, workout: dict) -> str:
    """Crea un nuevo entreno en ForzudoOS."""
    body = {
        "parent": {"database_id": database_id},
        "properties": {
            "Ejercicio": {"title": [{"text": {"content": workout["ejercicio"]}}]},
            "Fecha": {"date": {"start": workout["fecha"]}},
            "Día BBB": {"select": {"name": workout.get("dia_bbb", "")}},
            "Semana": {"number": workout.get("semana", 0)},
            "Peso Top": {"number": workout.get("peso_top", 0)},
            "Reps": {"rich_text": [{"text": {"content": workout.get("reps", "")}}]},
            "Volumen": {"number": workout.get("volumen", 0)},
            "Hevy ID": {"rich_text": [{"text": {"content": workout.get("hevy_id", "")}}]},
            "Sincronizado": {"checkbox": True},
        },
    }
    
    result = _post("/pages", body)
    return result["id"]


def get_recent_workouts(
    database_id: str,
    days: int = 7,
) -> list[WorkoutEntry]:
    """Obtiene entrenamientos recientes de ForzudoOS."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    body = {
        "filter": {
            "property": "Fecha",
            "date": {"on_or_after": since},
        },
        "sorts": [{"property": "Fecha", "direction": "descending"}],
        "page_size": 100,
    }
    
    data = _post(f"/databases/{database_id}/query", body)
    
    results = []
    for page in data.get("results", []):
        props = page.get("properties", {})
        
        def get_title(prop: str) -> str:
            t = props.get(prop, {}).get("title", [])
            return t[0].get("plain_text", "") if t else ""
        
        def get_text(prop: str) -> str:
            rt = props.get(prop, {}).get("rich_text", [])
            return rt[0].get("plain_text", "") if rt else ""
        
        date_str = props.get("Fecha", {}).get("date", {}).get("start", "")
        
        results.append(WorkoutEntry(
            ejercicio=get_title("Ejercicio"),
            fecha=datetime.fromisoformat(date_str) if date_str else datetime.now(),
            dia_bbb=props.get("Día BBB", {}).get("select", {}).get("name", ""),
            semana=props.get("Semana", {}).get("number", 0) or 0,
            peso_top=props.get("Peso Top", {}).get("number", 0.0) or 0.0,
            reps=get_text("Reps"),
            volumen=props.get("Volumen", {}).get("number", 0.0) or 0.0,
            hevy_id=get_text("Hevy ID"),
        ))
    
    return results


def get_last_workout(database_id: str) -> WorkoutEntry | None:
    """Obtiene el último entrenamiento registrado."""
    workouts = get_recent_workouts(database_id, days=30)
    return workouts[0] if workouts else None


# =============================================================================
# CONFIGURACIÓN DEL SISTEMA
# =============================================================================


def setup_forzudo_notion(parent_page_id: str | None = None) -> dict[str, str]:
    """Setup inicial: crea todas las bases de datos necesarias.
    
    Returns:
        Dict con los IDs de las bases de datos creadas.
    """
    print("🏗️ Creando bases de datos de ForzudoOS en Notion...")
    
    reminders_id = create_reminders_database(parent_page_id)
    print(f"✅ Recordatorios: {reminders_id}")
    
    workouts_id = create_workouts_database(parent_page_id)
    print(f"✅ Entrenos: {workouts_id}")
    
    return {
        "reminders_db": reminders_id,
        "workouts_db": workouts_id,
    }
