"""CLI de ForzudoOS."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main() -> int:
    """Entry point principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="ForzudoOS - Sistema de recordatorios inteligentes"
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")
    
    # Comando: setup
    subparsers.add_parser("setup", help="Crear bases de datos en Notion")
    
    # Comando: parse
    parse_parser = subparsers.add_parser("parse", help="Parsear frase de recordatorio")
    parse_parser.add_argument("text", help="Texto a parsear")
    
    # Comando: recordar
    remind_parser = subparsers.add_parser("recordar", help="Crear recordatorio")
    remind_parser.add_argument("text", help="Texto del recordatorio")
    remind_parser.add_argument("--user", default="juan", help="ID de usuario")
    
    # Comando: status
    status_parser = subparsers.add_parser("status", help="Ver estado actual")
    status_parser.add_argument("--workouts-db", help="ID de base de datos de entrenos")
    
    # Comando: check
    subparsers.add_parser("check", help="Ejecutar checks de recordatorios")
    
    # Comando: sync
    sync_parser = subparsers.add_parser("sync", help="Sincronizar entreno desde BBD")
    sync_parser.add_argument("--data", required=True, help="JSON con datos del entreno")
    sync_parser.add_argument("--workouts-db", help="ID de base de datos de entrenos")
    
    # Comando: dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Generar datos para dashboard")
    dash_parser.add_argument("--output", default="docs/data.json", help="Ruta de salida")
    
    # Comando: cron
    cron_parser = subparsers.add_parser("cron", help="Gestión de cron jobs")
    cron_subparsers = cron_parser.add_subparsers(dest="cron_command")
    
    cron_subparsers.add_parser("list", help="Listar jobs")
    cron_export = cron_subparsers.add_parser("export", help="Exportar jobs")
    cron_export.add_argument("--output", default="forzudo-cron-jobs.json")
    cron_subparsers.add_parser("register", help="Instrucciones de registro")
    
    args, remaining = parser.parse_known_args()
    
    if args.command == "setup":
        return cmd_setup(remaining)
    
    if args.command == "parse":
        return cmd_parse(args)
    
    if args.command == "recordar":
        return cmd_recordar(args)
    
    if args.command == "status":
        return cmd_status(remaining)
    
    if args.command == "check":
        return cmd_check()
    
    if args.command == "sync":
        return cmd_sync(remaining)
    
    if args.command == "dashboard":
        return cmd_dashboard(args)
    
    if args.command == "cron":
        return cmd_cron(args, cron_parser)
    
    parser.print_help()
    return 1


def cmd_setup(args: list[str]) -> int:
    """Setup de ForzudoOS en Notion."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup de ForzudoOS en Notion")
    parser.add_argument("--parent-page", help="ID de página padre en Notion")
    pargs = parser.parse_args(args)
    
    parent = pargs.parent_page or os.environ.get("FORZUDO_PARENT_PAGE")
    
    if not parent:
        print("❌ Se necesita --parent-page o FORZUDO_PARENT_PAGE")
        return 1
    
    try:
        from forzudo.notion import setup_forzudo_notion
        
        print(f"🏗️ Configurando ForzudoOS en Notion...")
        dbs = setup_forzudo_notion(parent)
        
        print("\n✅ Setup completado!")
        print(f'FORZUDO_REMINDERS_DB="{dbs["reminders_db"]}"')
        print(f'FORZUDO_WORKOUTS_DB="{dbs["workouts_db"]}"')
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_parse(args) -> int:
    """Parsear frase de recordatorio."""
    from forzudo.parser import parse_reminder
    
    intent = parse_reminder(args.text)
    print(f"📝 Texto: {intent.raw_text}")
    print(f"🔔 Trigger: {intent.trigger_type.name}")
    print(f"📊 Datos: {intent.trigger_data}")
    print(f"⚡ Acción: {intent.action_type.name}")
    print(f"\n🔧 Job:\n{intent.to_cron_job()}")
    return 0


def cmd_recordar(args) -> int:
    """Crear recordatorio."""
    from forzudo.parser import parse_reminder
    from forzudo.scheduler import Scheduler
    
    intent = parse_reminder(args.text)
    scheduler = Scheduler()
    job = scheduler.create_job(args.user, intent)
    print(f"✅ Recordatorio creado: {job.id}")
    return 0


def cmd_status(args: list[str]) -> int:
    """Ver estado actual."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Estado actual")
    parser.add_argument("--workouts-db", help="ID de base de datos de entrenos")
    pargs = parser.parse_args(args)
    
    workouts_db = pargs.workouts_db or os.environ.get("FORZUDO_WORKOUTS_DB")
    
    from forzudo.context import get_quick_status
    
    if workouts_db:
        try:
            from forzudo.notion import get_last_workout
            last = get_last_workout(workouts_db)
            print(get_quick_status(last))
            return 0
        except Exception as e:
            print(f"⚠️ No se pudo leer de Notion: {e}\n")
    
    print(get_quick_status())
    return 0


def cmd_check() -> int:
    """Ejecutar checks de recordatorios."""
    from forzudo.scheduler import Scheduler
    
    scheduler = Scheduler()
    triggered = scheduler.run_checks()
    
    if not triggered:
        print("✅ No hay recordatorios pendientes")
        return 0
    
    print(f"🔔 {len(triggered)} recordatorio(s) disparado(s):\n")
    for t in triggered:
        print(f"Job: {t['job_id']}")
        print(f"Mensaje:\n{t['message']}")
        print("-" * 40)
    return 0


def cmd_sync(args: list[str]) -> int:
    """Sincronizar entreno desde BBD."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Sincronizar entreno desde BBD")
    parser.add_argument("--data", required=True, help="JSON con datos del entreno")
    parser.add_argument("--workouts-db", help="ID de base de datos de entrenos")
    pargs = parser.parse_args(args)
    
    workouts_db = pargs.workouts_db or os.environ.get("FORZUDO_WORKOUTS_DB")
    
    if not workouts_db:
        print("❌ Se necesita --workouts-db o FORZUDO_WORKOUTS_DB")
        return 1
    
    try:
        data = json.loads(pargs.data)
        from forzudo.notion import sync_workout_from_bbd
        
        page_id = sync_workout_from_bbd(workouts_db, data)
        print(f"✅ Entreno sincronizado: {page_id}")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_dashboard(args) -> int:
    """Generar datos para dashboard."""
    from forzudo.dashboard_generator import cmd_generate_dashboard
    return cmd_generate_dashboard([f"--output={args.output}"])


def cmd_cron(args, cron_parser) -> int:
    """Gestión de cron jobs."""
    if args.cron_command == "list":
        from forzudo.cron_manager import cmd_cron_list
        return cmd_cron_list([])
    elif args.cron_command == "export":
        from forzudo.cron_manager import cmd_cron_export
        return cmd_cron_export([f"--output={args.output}"])
    elif args.cron_command == "register":
        from forzudo.cron_manager import cmd_cron_register
        return cmd_cron_register([])
    else:
        cron_parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
