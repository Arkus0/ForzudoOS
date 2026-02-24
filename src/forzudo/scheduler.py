"""Scheduler - Gestión de recordatorios programados con Notion backend."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from forzudo.parser import ReminderIntent


class JobStatus(Enum):
    """Estado de un job."""
    ACTIVE = "activo"
    PAUSED = "pausado"
    TRIGGERED = "disparado"
    COMPLETED = "completado"


@dataclass
class ReminderJob:
    """Un job de recordatorio."""
    
    id: str
    user_id: str
    intent: ReminderIntent
    status: JobStatus
    created_at: str
    notion_page_id: str | None = None
    last_checked: str | None = None
    trigger_count: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "intent": {
                "raw_text": self.intent.raw_text,
                "trigger_type": self.intent.trigger_type.name,
                "trigger_data": self.intent.trigger_data,
                "action_type": self.intent.action_type.name,
                "action_data": self.intent.action_data,
                "context_needed": self.intent.context_needed,
            },
            "status": self.status.value,
            "created_at": self.created_at,
            "notion_page_id": self.notion_page_id,
            "last_checked": self.last_checked,
            "trigger_count": self.trigger_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> ReminderJob:
        from forzudo.parser import ActionType, TriggerType
        
        intent_data = data["intent"]
        intent = ReminderIntent(
            raw_text=intent_data["raw_text"],
            trigger_type=TriggerType[intent_data["trigger_type"]],
            trigger_data=intent_data["trigger_data"],
            action_type=ActionType[intent_data["action_type"]],
            action_data=intent_data["action_data"],
            context_needed=intent_data["context_needed"],
        )
        
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            intent=intent,
            status=JobStatus(data["status"]),
            created_at=data["created_at"],
            notion_page_id=data.get("notion_page_id"),
            last_checked=data.get("last_checked"),
            trigger_count=data.get("trigger_count", 0),
        )


class JobStore:
    """Almacenamiento local de jobs (fallback si Notion no está disponible)."""
    
    def __init__(self, data_dir: str | None = None) -> None:
        self.data_dir = Path(data_dir or os.environ.get("FORZUDO_DATA", "/tmp/forzudo"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_file = self.data_dir / "jobs.json"
    
    def _load_all(self) -> dict[str, dict]:
        if not self.jobs_file.exists():
            return {}
        with open(self.jobs_file) as f:
            return json.load(f)
    
    def _save_all(self, jobs: dict[str, dict]) -> None:
        with open(self.jobs_file, "w") as f:
            json.dump(jobs, f, indent=2)
    
    def save(self, job: ReminderJob) -> None:
        jobs = self._load_all()
        jobs[job.id] = job.to_dict()
        self._save_all(jobs)
    
    def get(self, job_id: str) -> ReminderJob | None:
        jobs = self._load_all()
        if job_id not in jobs:
            return None
        return ReminderJob.from_dict(jobs[job_id])
    
    def get_all_active(self) -> list[ReminderJob]:
        jobs = self._load_all()
        return [
            ReminderJob.from_dict(j) 
            for j in jobs.values() 
            if j["status"] == JobStatus.ACTIVE.value
        ]
    
    def get_for_user(self, user_id: str) -> list[ReminderJob]:
        jobs = self._load_all()
        return [
            ReminderJob.from_dict(j)
            for j in jobs.values()
            if j["user_id"] == user_id
        ]
    
    def update_status(self, job_id: str, status: JobStatus) -> None:
        jobs = self._load_all()
        if job_id in jobs:
            jobs[job_id]["status"] = status.value
            self._save_all(jobs)


class NotionJobStore:
    """Almacenamiento de jobs en Notion."""
    
    def __init__(self, database_id: str | None = None) -> None:
        self.database_id = database_id or os.environ.get("FORZUDO_REMINDERS_DB", "")
    
    def save(self, job: ReminderJob) -> None:
        """Guarda un job en Notion."""
        if not self.database_id:
            raise ValueError("FORZUDO_REMINDERS_DB no configurado")
        
        from forzudo.notion import create_reminder
        
        notion_id = create_reminder(
            database_id=self.database_id,
            nombre=job.intent.raw_text[:50],  # Truncar para título
            tipo=job.intent.trigger_type.name.lower(),
            condicion=job.intent.to_cron_job(),
            user_id=job.user_id,
        )
        job.notion_page_id = notion_id
    
    def get_all_active(self) -> list[ReminderJob]:
        """Obtiene todos los jobs activos desde Notion."""
        if not self.database_id:
            return []
        
        from forzudo.notion import query_reminders
        
        entries = query_reminders(self.database_id, estado="activo")
        
        jobs = []
        for e in entries:
            # Convertir ReminderEntry a ReminderJob
            intent = ReminderIntent(
                raw_text=e.nombre,
                trigger_type=self._str_to_trigger(e.tipo),
                trigger_data=e.condicion,
                action_type=ReminderIntent.parse(e.nombre).action_type,
                action_data={},
                context_needed=[],
            )
            
            jobs.append(ReminderJob(
                id=e.id[:8],  # Usar parte del ID de Notion
                user_id=e.user_id,
                intent=intent,
                status=JobStatus(e.estado),
                created_at=e.ultimo_check.isoformat() if e.ultimo_check else "",
                notion_page_id=e.id,
                last_checked=e.ultimo_check.isoformat() if e.ultimo_check else None,
                trigger_count=e.contador,
            ))
        
        return jobs
    
    def _str_to_trigger(self, tipo: str) -> Any:
        """Convierte string de tipo a TriggerType."""
        from forzudo.parser import TriggerType
        
        mapping = {
            "condicional": TriggerType.CONDITIONAL,
            "temporal": TriggerType.TIME_BASED,
            "recurrente": TriggerType.RECURRING,
            "evento": TriggerType.EVENT_BASED,
        }
        return mapping.get(tipo, TriggerType.TIME_BASED)


class Scheduler:
    """Orquestador de recordatorios."""
    
    def __init__(
        self,
        local_store: JobStore | None = None,
        notion_store: NotionJobStore | None = None,
    ) -> None:
        self.local = local_store or JobStore()
        self.notion = notion_store
        
        # Intentar usar Notion si está configurado
        if notion_store is None and os.environ.get("FORZUDO_REMINDERS_DB"):
            self.notion = NotionJobStore()
    
    def create_job(self, user_id: str, intent: ReminderIntent) -> ReminderJob:
        """Crea un nuevo job desde una intención parseada."""
        from datetime import datetime
        import uuid
        
        job = ReminderJob(
            id=str(uuid.uuid4())[:8],
            user_id=user_id,
            intent=intent,
            status=JobStatus.ACTIVE,
            created_at=datetime.now().isoformat(),
        )
        
        # Guardar localmente siempre
        self.local.save(job)
        
        # Intentar guardar en Notion también
        if self.notion:
            try:
                self.notion.save(job)
            except Exception as e:
                print(f"⚠️ No se pudo guardar en Notion: {e}")
        
        return job
    
    def check_job(self, job: ReminderJob) -> dict | None:
        """Evalúa si un job debe dispararse."""
        from datetime import datetime
        from forzudo.context import build_context
        from forzudo.notion import WorkoutEntry
        
        job.last_checked = datetime.now().isoformat()
        
        intent = job.intent
        
        # Para jobs condicionales, necesitamos datos de entrenamiento
        if intent.trigger_type.name == "CONDITIONAL":
            condition = intent.trigger_data.get("condition")
            
            if condition == "no_training":
                threshold = intent.trigger_data.get("hours", 48)
                
                # Intentar obtener último entreno
                last_workout = None
                try:
                    from forzudo.notion import get_last_workout
                    workouts_db = os.environ.get("FORZUDO_WORKOUTS_DB")
                    if workouts_db:
                        last_workout = get_last_workout(workouts_db)
                except Exception:
                    pass
                
                # Si no hay datos, usar contexto estimado
                ctx = build_context(last_workout)
                
                if ctx.hours_since_last is None:
                    return None
                
                if ctx.hours_since_last > threshold:
                    job.trigger_count += 1
                    self.local.save(job)
                    
                    return {
                        "triggered": True,
                        "reason": f"No training for {ctx.hours_since_last:.0f}h",
                        "context": ctx,
                        "message": self._build_message(intent, ctx),
                    }
        
        elif intent.trigger_type.name == "EVENT_BASED":
            event = intent.trigger_data.get("event")
            
            if event == "deload":
                days_before = intent.trigger_data.get("days_before", 3)
                
                ctx = build_context()
                
                if ctx.days_until_deload is not None and ctx.days_until_deload <= days_before:
                    return {
                        "triggered": True,
                        "reason": f"Deload in {ctx.days_until_deload} days",
                        "context": ctx,
                        "message": self._build_message(intent, ctx),
                    }
        
        self.local.save(job)
        return None
    
    def _build_message(self, intent: ReminderIntent, ctx: Any) -> str:
        """Construye el mensaje final con contexto."""
        from forzudo.context import format_context_message
        return format_context_message(ctx)
    
    def run_checks(self) -> list[dict]:
        """Ejecuta checks de todos los jobs activos."""
        triggered = []
        
        # Obtener jobs de Notion si está disponible, si no, de local
        jobs = []
        if self.notion:
            try:
                jobs = self.notion.get_all_active()
            except Exception:
                pass
        
        if not jobs:
            jobs = self.local.get_all_active()
        
        for job in jobs:
            result = self.check_job(job)
            if result and result.get("triggered"):
                triggered.append({
                    "job_id": job.id,
                    "user_id": job.user_id,
                    **result,
                })
        
        return triggered
