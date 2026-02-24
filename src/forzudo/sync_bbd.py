"""Sincronización de entrenos desde BBD Analytics a ForzudoOS."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from forzudo.notion import create_workout_entry, get_recent_workouts as get_forzudo_workouts


# IDs
BBD_LOGBOOK_DB = "31e7df96-6afb-4b58-a34c-817cb2bf887d"


def fetch_bbd_workouts(limit: int = 50) -> list[dict]:
    """Obtiene entrenos de BBD Analytics (solo lectura)."""
    import requests
    import time
    
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise ValueError("NOTION_TOKEN no configurado")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    
    all_workouts = []
    has_more = True
    start_cursor = None
    
    while has_more and len(all_workouts) < limit:
        body = {"page_size": min(100, limit - len(all_workouts))}
        if start_cursor:
            body["start_cursor"] = start_cursor
        
        # Rate limit
        time.sleep(0.35)
        
        response = requests.post(
            f"https://api.notion.com/v1/databases/{BBD_LOGBOOK_DB}/query",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        
        data = response.json()
        all_workouts.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    
    return all_workouts


def parse_bbd_workout(page: dict) -> dict | None:
    """Parsea un entreno de BBD al formato de ForzudoOS."""
    props = page.get("properties", {})
    
    def get_title(prop: str) -> str:
        t = props.get(prop, {}).get("title", [])
        return t[0].get("plain_text", "") if t else ""
    
    def get_text(prop: str) -> str:
        rt = props.get(prop, {}).get("rich_text", [])
        return rt[0].get("plain_text", "") if rt else ""
    
    def get_number(prop: str) -> float:
        return props.get(prop, {}).get("number") or 0
    
    def get_select(prop: str) -> str:
        return props.get(prop, {}).get("select", {}).get("name", "")
    
    ejercicio = get_title("Ejercicio")
    if not ejercicio:
        return None
    
    fecha_str = props.get("Fecha", {}).get("date", {}).get("start", "")
    
    # Día BBB no puede estar vacío, usar valor por defecto
    dia_bbb = get_select("Día")
    if not dia_bbb:
        dia_bbb = "Sin día"
    
    return {
        "ejercicio": ejercicio,
        "fecha": fecha_str,
        "dia_bbb": dia_bbb,
        "semana": int(get_number("Semana")),
        "peso_top": get_number("Top Set"),
        "reps": get_text("Reps"),
        "volumen": get_number("Series") * get_number("Top Set") * 10,
        "hevy_id": get_text("Hevy ID"),
    }


def sync_bbd_to_forzudo(dry_run: bool = False) -> dict:
    """Sincroniza entrenos de BBD a ForzudoOS.
    
    Args:
        dry_run: Si True, solo muestra lo que sincronizaría sin hacer cambios
        
    Returns:
        Estadísticas de la sincronización
    """
    print("🔄 Sincronizando BBD Analytics → ForzudoOS...")
    
    # Obtener entrenos de BBD
    bbd_workouts = fetch_bbd_workouts(limit=100)
    print(f"📥 {len(bbd_workouts)} entrenos encontrados en BBD")
    
    # Obtener entrenos ya sincronizados en ForzudoOS
    forzudo_db = os.environ.get("FORZUDO_WORKOUTS_DB")
    if not forzudo_db:
        raise ValueError("FORZUDO_WORKOUTS_DB no configurado")
    
    existing = get_forzudo_workouts(forzudo_db, days=90)
    existing_hevy_ids = {w.hevy_id for w in existing if w.hevy_id}
    
    print(f"📋 {len(existing)} entrenos ya en ForzudoOS")
    
    # Filtrar los que no están sincronizados
    to_sync = []
    for page in bbd_workouts:
        hevy_id = page.get("properties", {}).get("Hevy ID", {}).get("rich_text", [{}])[0].get("plain_text", "")
        
        if hevy_id and hevy_id in existing_hevy_ids:
            continue  # Ya sincronizado
        
        workout = parse_bbd_workout(page)
        if workout:
            to_sync.append(workout)
    
    print(f"🆕 {len(to_sync)} entrenos nuevos para sincronizar")
    
    if dry_run:
        print("\n🔍 DRY RUN - No se realizarán cambios")
        for w in to_sync[:5]:
            print(f"  - {w['ejercicio']} ({w['fecha']})")
        if len(to_sync) > 5:
            print(f"  ... y {len(to_sync) - 5} más")
        return {"synced": 0, "skipped": len(bbd_workouts) - len(to_sync), "dry_run": True}
    
    # Sincronizar
    synced = 0
    errors = 0
    
    for workout in to_sync:
        try:
            create_workout_entry(forzudo_db, workout)
            synced += 1
            print(f"  ✅ {workout['ejercicio']}")
        except Exception as e:
            errors += 1
            print(f"  ❌ {workout['ejercicio']}: {e}")
    
    print(f"\n✅ Sincronización completada:")
    print(f"   {synced} entrenos sincronizados")
    print(f"   {len(to_sync) - synced - errors} omitidos")
    print(f"   {errors} errores")
    
    return {
        "synced": synced,
        "skipped": len(to_sync) - synced - errors,
        "errors": errors,
        "total_bbd": len(bbd_workouts),
    }


def cmd_sync_bbd(args: list[str]) -> int:
    """Comando CLI para sincronizar desde BBD."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sincronizar desde BBD Analytics")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin hacer cambios")
    pargs = parser.parse_args(args)
    
    try:
        result = sync_bbd_to_forzudo(dry_run=pargs.dry_run)
        return 0 if result.get("errors", 0) == 0 else 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(cmd_sync_bbd(sys.argv[1:]))
