"""Parser de lenguaje natural para recordatorios."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Self


class TriggerType(Enum):
    """Tipos de triggers para recordatorios."""
    
    TIME_BASED = auto()      # "mañana a las 9", "en 2 horas"
    CONDITIONAL = auto()     # "si no entreno en 48h"
    RECURRING = auto()       # "todos los lunes"
    EVENT_BASED = auto()     # "3 días antes del deload"


class ActionType(Enum):
    """Tipos de acciones cuando se dispara un recordatorio."""
    
    NOTIFY = auto()          # Enviar mensaje
    ASK = auto()             # Preguntar algo
    REMIND = auto()          # Recordar con contexto


@dataclass(frozen=True)
class ReminderIntent:
    """Intención parseada de una frase de recordatorio."""
    
    raw_text: str
    trigger_type: TriggerType
    trigger_data: dict
    action_type: ActionType
    action_data: dict
    context_needed: list[str]  # qué datos necesitamos enriquecer
    
    @classmethod
    def parse(cls, text: str) -> Self:
        """Parsea una frase en una intención estructurada."""
        text_lower = text.lower().strip()
        
        # Patrones de detección
        patterns = {
            "no_training": r"no\s+(?:he\s+)?entren(?:o|ado)\s+(?:en\s+)?(\d+)\s*([hd])?",
            "deload_warning": r"(?:av[íi]same|avisa|recuerda).*\bdeload\b.*?(\d+)\s*d[ií]as?\s*(?:antes)?",
            "next_session": r"(?:qu[eé]\s+)?toca\s+(?:hoy|mañana|pasado)?",
            "time_based": r"(?:recu[eé]rdame|av[íi]same)\s+(?:a?l?\s*)?(?:las\s+)?(\d+)(?::(\d+))?\s*(am|pm)?",
            "recurring": r"(?:cada|todos\s+los)\s+(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)",
        }
        
        # Detectar condición: "si no entreno en X horas/días"
        if match := re.search(patterns["no_training"], text_lower):
            amount = int(match.group(1))
            unit = match.group(2) if match.group(2) else "h"
            hours = amount if unit == "h" else amount * 24
            return cls(
                raw_text=text,
                trigger_type=TriggerType.CONDITIONAL,
                trigger_data={
                    "condition": "no_training",
                    "hours": hours,
                    "check_interval": min(hours // 4, 6),
                },
                action_type=ActionType.REMIND,
                action_data={"message": f"Llevas más de {amount}{unit} sin entrenar"},
                context_needed=["last_workout", "next_session", "current_cycle"],
            )
        
        # Detectar aviso de deload
        if match := re.search(patterns["deload_warning"], text_lower):
            days = int(match.group(1))
            return cls(
                raw_text=text,
                trigger_type=TriggerType.EVENT_BASED,
                trigger_data={
                    "event": "deload",
                    "days_before": days,
                },
                action_type=ActionType.REMIND,
                action_data={"message": f"Deload en {days} días"},
                context_needed=["cycle_position", "deload_date"],
            )
        
        # Detectar consulta de próximo entreno
        if re.search(patterns["next_session"], text_lower):
            return cls(
                raw_text=text,
                trigger_type=TriggerType.TIME_BASED,
                trigger_data={"when": "now"},
                action_type=ActionType.ASK,
                action_data={"query": "next_session"},
                context_needed=["next_session", "current_cycle", "last_workout"],
            )
        
        # Por defecto: notificación simple
        return cls(
            raw_text=text,
            trigger_type=TriggerType.TIME_BASED,
            trigger_data={"when": "unspecified"},
            action_type=ActionType.NOTIFY,
            action_data={"message": text},
            context_needed=[],
        )
    
    def to_cron_job(self) -> dict:
        """Convierte la intención en un job programable."""
        if self.trigger_type == TriggerType.CONDITIONAL:
            return {
                "type": "conditional",
                "check_every_hours": self.trigger_data.get("check_interval", 6),
                "condition": self.trigger_data["condition"],
                "threshold_hours": self.trigger_data["hours"],
                "action": "notify_with_context",
                "context": self.context_needed,
            }
        
        if self.trigger_type == TriggerType.EVENT_BASED:
            return {
                "type": "event_based",
                "event": self.trigger_data["event"],
                "days_before": self.trigger_data.get("days_before", 3),
                "action": "notify_with_context",
                "context": self.context_needed,
            }
        
        return {
            "type": "simple",
            "action": "notify",
            "message": self.action_data.get("message", ""),
        }


def parse_reminder(text: str) -> ReminderIntent:
    """Función pública para parsear recordatorios."""
    return ReminderIntent.parse(text)
