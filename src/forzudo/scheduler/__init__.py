"""Scheduler - Gestión de recordatorios programados."""

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
    ACTIVE = "active"
    PAUSED = "paused"
    TRIGGERED = "triggered"
    COMPLETED = "completed"


@dataclass
class ReminderJob:
    """Un job de recordatorio programado."""
    
    id: str
    user_id: str
    intent: ReminderIntent
    status: JobStatus
    created_at: str
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
            last_checked=data.get("last_checked"),
            trigger_count=data.get("trigger_count", 0),
        )


class JobStore:
    """Almacenamiento de jobs."""
    
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


class Scheduler:
    """Orquestador de recordatorios."""
    
    def __init__(self, store: JobStore | None = None) -> None:
        self.store = store or JobStore()
    
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
        
        self.store.save(job)
        return job
    
    def check_job(self, job: ReminderJob) -> dict | None:
        """Evalúa si un job debe dispararse."""
        from datetime import datetime
        from forzudo.context import build_context
        
        # Actualizar timestamp de check
        job.last_checked = datetime.now().isoformat()
        
        intent = job.intent
        ctx = build_context()
        
        # Evaluar según tipo de trigger
        if intent.trigger_type.name == "CONDITIONAL":
            condition = intent.trigger_data.get("condition")
            
            if condition == "no_training":
                threshold = intent.trigger_data.get("hours", 48)
                
                if ctx.hours_since_last is None:
                    return None  # No hay datos
                
                if ctx.hours_since_last > threshold:
                    job.trigger_count += 1
                    self.store.save(job)
                    
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
                
                if ctx.days_until_deload is not None and ctx.days_until_deload <= days_before:
                    return {
                        "triggered": True,
                        "reason": f"Deload in {ctx.days_until_deload} days",
                        "context": ctx,
                        "message": self._build_message(intent, ctx),
                    }
        
        self.store.save(job)
        return None
    
    def _build_message(self, intent: ReminderIntent, ctx: Any) -> str:
        """Construye el mensaje final con contexto."""
        from forzudo.context import format_reminder_with_context
        return format_reminder_with_context(intent.raw_text, ctx)
    
    def run_checks(self) -> list[dict]:
        """Ejecuta checks de todos los jobs activos."""
        triggered = []
        
        for job in self.store.get_all_active():
            result = self.check_job(job)
            if result and result.get("triggered"):
                triggered.append({
                    "job_id": job.id,
                    "user_id": job.user_id,
                    **result,
                })
        
        return triggered
