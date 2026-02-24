"""CLI de ForzudoOS."""

from __future__ import annotations

import os
import sys

# Añadir src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from forzudo.context import get_quick_status
from forzudo.parser import parse_reminder
from forzudo.scheduler import Scheduler


def cmd_setup(args: list[str]) -> int:
    """Comando setup: crea bases de datos en Notion."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup de ForzudoOS en Notion")
    parser.add_argument("--parent-page", help="ID de página padre en Notion")
    pargs = parser.parse_args(args)
    
    parent = pargs.parent_page or os.environ.get("FORZUDO_PARENT_PAGE")
    
    if not parent:
        print("❌ Se necesita --parent-page o FORZUDO_PARENT_PAGE")
        print("\nPara obtener el ID de una página:")
        print("1. Abre Notion en el navegador")
        print("2. Ve a la página donde quieras crear las bases de datos")
        print("3. La URL tiene este formato: https://notion.so/workspace/[PAGE_ID]")
        print("4. Copia el PAGE_ID (32 caracteres)")
        return 1
    
    try:
        from forzudo.notion import setup_forzudo_notion
        
        print(f"🏗️ Configurando ForzudoOS en Notion...")
        print(f"   Página padre: {parent}")
        
        dbs = setup_forzudo_notion(parent)
        
        print("\n✅ Setup completado!")
        print(f"\nAñade estas variables a tu .env:")
        print(f'FORZUDO_REMINDERS_DB="{dbs["reminders_db"]}"')
        print(f'FORZUDO_WORKOUTS_DB="{dbs["workouts_db"]}"')
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_status(args: list[str]) -> int:
    """Muestra estado actual."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Estado actual")
    parser.add_argument("--workouts-db", help="ID de base de datos de entrenos")
    pargs = parser.parse_args(args)
    
    workouts_db = pargs.workouts_db or os.environ.get("FORZUDO_WORKOUTS_DB")
    
    if workouts_db:
        # Intentar leer desde Notion
        try:
            from forzudo.notion import get_last_workout
            last = get_last_workout(workouts_db)
            print(get_quick_status(last))
            return 0
        except Exception as e:
            print(f"⚠️ No se pudo leer de Notion: {e}")
            print("Mostrando estado estimado:\n")
    
    print(get_quick_status())
    return 0


def cmd_sync(args: list[str]) -> int:
    """Sincroniza entreno desde BBD Analytics."""
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


def cmd_cron(args: list[str]) -> int:
    """Comandos de gestión de cron jobs."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gestión de cron jobs")
    subparsers = parser.add_subparsers(dest="cron_command", help="Subcomandos")
    
    # cron list
    subparsers.add_parser("list", help="Listar jobs de ForzudoOS")
    
    # cron export
    export_parser = subparsers.add_parser("export", help="Exportar jobs a archivo")
    export_parser.add_argument("--output", default="forzudo-cron-jobs.json")
    
    # cron register
    subparsers.add_parser("register", help="Mostrar instrucciones de registro")
    
    # Si no hay subcomando, mostrar ayuda
    if not args or args[0] not in ["list", "export", "register"]:
        parser.print_help()
        return 1
    
    # Parsear con el subcomando como primer argumento
    pargs = parser.parse_args(args[:1])
    remaining = args[1:] if len(args) > 1 else []
    
    if pargs.cron_command == "list":
        from forzudo.cron_manager import cmd_cron_list
        return cmd_cron_list(remaining)
    
    if pargs.cron_command == "export":
        from forzudo.cron_manager import cmd_cron_export
        return cmd_cron_export([f"--output={pargs.output}"] + remaining)
    
    if pargs.cron_command == "register":
        from forzudo.cron_manager import cmd_cron_register
        return cmd_cron_register(remaining)
    
    parser.print_help()
    return 1


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
    
    # Comando: cron (con subcomandos directos)
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
        intent = parse_reminder(args.text)
        print(f"📝 Texto: {intent.raw_text}")
        print(f"🔔 Trigger: {intent.trigger_type.name}")
        print(f"📊 Datos: {intent.trigger_data}")
        print(f"⚡ Acción: {intent.action_type.name}")
        print(f"📋 Contexto: {intent.context_needed}")
        print(f"\n🔧 Job:\n{intent.to_cron_job()}")
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
        return cmd_status(remaining)
    
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
    
    if args.command == "sync":
        return cmd_sync(remaining)
    
    if args.command == "cron":
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
    
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
