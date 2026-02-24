"""CLI de ForzudoOS."""

from __future__ import annotations

import os
import sys

# Añadir src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from forzudo.context import get_quick_status
from forzudo.parser import parse_reminder
from forzudo.scheduler import Scheduler


def main() -> int:
    """Entry point principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ForzudoOS - Sistema de recordatorios inteligentes")
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")
    
    # Comando: parse
    parse_parser = subparsers.add_parser("parse", help="Parsear una frase de recordatorio")
    parse_parser.add_argument("text", help="Texto a parsear")
    
    # Comando: recordar
    remind_parser = subparsers.add_parser("recordar", help="Crear un recordatorio")
    remind_parser.add_argument("text", help="Texto del recordatorio")
    remind_parser.add_argument("--user", default="juan", help="ID de usuario")
    
    # Comando: status
    subparsers.add_parser("status", help="Ver estado actual")
    
    # Comando: check
    subparsers.add_parser("check", help="Ejecutar checks de recordatorios")
    
    args = parser.parse_args()
    
    if args.command == "parse":
        intent = parse_reminder(args.text)
        print(f"📝 Texto: {intent.raw_text}")
        print(f"🔔 Trigger: {intent.trigger_type.name}")
        print(f"📊 Datos: {intent.trigger_data}")
        print(f"⚡ Acción: {intent.action_type.name}")
        print(f"📋 Contexto necesario: {intent.context_needed}")
        print(f"\n🔧 Job config:\n{intent.to_cron_job()}")
        return 0
    
    if args.command == "recordar":
        intent = parse_reminder(args.text)
        scheduler = Scheduler()
        job = scheduler.create_job(args.user, intent)
        print(f"✅ Recordatorio creado: {job.id}")
        print(f"   Tipo: {intent.trigger_type.name}")
        print(f"   Estado: {job.status.value}")
        return 0
    
    if args.command == "status":
        print(get_quick_status())
        return 0
    
    if args.command == "check":
        scheduler = Scheduler()
        triggered = scheduler.run_checks()
        
        if not triggered:
            print("✅ No hay recordatorios pendientes")
            return 0
        
        print(f"🔔 {len(triggered)} recordatorio(s) disparado(s):\n")
        for t in triggered:
            print(f"Job: {t['job_id']}")
            print(f"Razón: {t['reason']}")
            print(f"Mensaje:\n{t['message']}")
            print("-" * 40)
        return 0
    
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
