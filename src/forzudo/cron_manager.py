"""Cron Manager - Integración con OpenClaw Cron."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class CronJob:
    """Representa un job de cron para OpenClaw."""
    
    id: str
    name: str
    schedule: dict[str, Any]  # Configuración de schedule
    payload: dict[str, Any]   # Qué ejecutar
    session_target: str = "isolated"
    enabled: bool = True
    
    def to_openclaw_job(self) -> dict:
        """Convierte a formato de job de OpenClaw."""
        return {
            "name": self.name,
            "schedule": self.schedule,
            "payload": self.payload,
            "sessionTarget": self.session_target,
            "enabled": self.enabled,
        }


class ForzudoCronManager:
    """Gestiona los cron jobs de ForzudoOS."""
    
    def __init__(self) -> None:
        self.jobs: list[CronJob] = []
    
    def create_check_workouts_job(
        self,
        user_id: str = "juan",
        check_interval_hours: int = 6,
    ) -> CronJob:
        """Crea un job que verifica si hay entrenos pendientes cada N horas."""
        return CronJob(
            id="check_workouts",
            name="ForzudoOS - Check Workouts",
            schedule={
                "kind": "every",
                "everyMs": check_interval_hours * 60 * 60 * 1000,  # ms
            },
            payload={
                "kind": "agentTurn",
                "message": f"""ForzudoOS Cron Job: Check Workouts

Ejecuta el check de recordatorios para el usuario {user_id}.

1. Cambia al directorio del proyecto:
   cd /root/.openclaw/workspace/projects/forzudo-system

2. Ejecuta el check:
   uv run forzudo check

3. Si hay recordatorios disparados, envía mensaje por Telegram al usuario.

4. Responde con:
   - Número de checks realizados
   - Recordatorios disparados (si hay)
   - Estado de la ejecución
""",
                "model": "kimi-coding/k2p5",
                "timeoutSeconds": 60,
            },
        )
    
    def create_daily_summary_job(
        self,
        user_id: str = "juan",
        hour: int = 7,
        minute: int = 0,
    ) -> CronJob:
        """Crea un job que envía resumen diario por la mañana."""
        # Calcular próximo horario
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        
        return CronJob(
            id="daily_summary",
            name="ForzudoOS - Daily Summary",
            schedule={
                "kind": "cron",
                "expr": f"{minute} {hour} * * *",  # Todos los días a la hora especificada
                "tz": "Europe/Madrid",
            },
            payload={
                "kind": "agentTurn",
                "message": f"""ForzudoOS Cron Job: Daily Summary

Envía resumen diario al usuario {user_id}.

1. Cambia al directorio del proyecto:
   cd /root/.openclaw/workspace/projects/forzudo-system

2. Obtén el estado:
   uv run forzudo status

3. Envía mensaje por Telegram con:
   - Saludo según hora
   - Estado del ciclo 5/3/1
   - Próximo entreno con pesos
   - Alertas relevantes
""",
                "model": "kimi-coding/k2p5",
                "timeoutSeconds": 60,
            },
        )
    
    def create_deload_warning_job(
        self,
        user_id: str = "juan",
        days_before: int = 3,
    ) -> CronJob:
        """Crea un job que avisa del deload con antelación."""
        return CronJob(
            id="deload_warning",
            name="ForzudoOS - Deload Warning",
            schedule={
                "kind": "every",
                "everyMs": 24 * 60 * 60 * 1000,  # Una vez al día
            },
            payload={
                "kind": "agentTurn",
                "message": f"""ForzudoOS Cron Job: Deload Warning

Verifica si estamos a {days_before} días o menos del deload.

1. Cambia al directorio:
   cd /root/.openclaw/workspace/projects/forzudo-system

2. Calcula el estado del ciclo y verifica:
   - Si week_in_macro >= {7 - days_before}
   - Si es así, envía aviso por Telegram

3. Mensaje tipo:
   "⏰ Deload en X días. Prepárate para la semana de recuperación."
""",
                "model": "kimi-coding/k2p5",
                "timeoutSeconds": 60,
            },
        )
    
    def get_all_jobs(self) -> list[CronJob]:
        """Devuelve todos los jobs estándar de ForzudoOS."""
        return [
            self.create_check_workouts_job(),
            self.create_daily_summary_job(),
            self.create_deload_warning_job(),
        ]
    
    def to_json(self) -> str:
        """Exporta todos los jobs a JSON."""
        return json.dumps(
            [job.to_openclaw_job() for job in self.get_all_jobs()],
            indent=2,
        )


def register_jobs_with_openclaw() -> None:
    """Registra los jobs de ForzudoOS en OpenClaw Cron.
    
    Esta función crea los jobs en el sistema de cron de OpenClaw.
    """
    manager = ForzudoCronManager()
    jobs = manager.get_all_jobs()
    
    print("📋 Jobs a crear:")
    for job in jobs:
        print(f"  - {job.name} ({job.id})")
    
    print("\n💡 Para registrar estos jobs, usa:")
    print("   openclaw cron add --job '$(cat forzudo-cron-jobs.json)'")
    print("\n   O manualmente con la herramienta cron:")
    
    for job in jobs:
        print(f"\n   # {job.name}")
        print(f"   cron add '{json.dumps(job.to_openclaw_job())}'")


def export_jobs_to_file(path: str = "forzudo-cron-jobs.json") -> None:
    """Exporta los jobs a un archivo JSON."""
    manager = ForzudoCronManager()
    
    jobs_data = [job.to_openclaw_job() for job in manager.get_all_jobs()]
    
    with open(path, "w") as f:
        json.dump(jobs_data, f, indent=2)
    
    print(f"✅ Jobs exportados a: {path}")
    print(f"   Total: {len(jobs_data)} jobs")


# =============================================================================
# COMANDOS CLI PARA CRON
# =============================================================================


def cmd_cron_export(args: list[str]) -> int:
    """Exporta jobs de cron a archivo."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Exportar jobs de cron")
    parser.add_argument("--output", default="forzudo-cron-jobs.json", help="Archivo de salida")
    pargs = parser.parse_args(args)
    
    export_jobs_to_file(pargs.output)
    return 0


def cmd_cron_register(args: list[str]) -> int:
    """Muestra instrucciones para registrar jobs."""
    register_jobs_with_openclaw()
    return 0


def cmd_cron_list(args: list[str]) -> int:
    """Lista jobs de ForzudoOS."""
    manager = ForzudoCronManager()
    
    print("🦍 ForzudoOS - Cron Jobs\n")
    
    for job in manager.get_all_jobs():
        print(f"📌 {job.name}")
        print(f"   ID: {job.id}")
        print(f"   Schedule: {job.schedule}")
        print()
    
    return 0
