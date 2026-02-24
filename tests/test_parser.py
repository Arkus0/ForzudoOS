"""Tests del parser de recordatorios."""

import pytest

from forzudo.parser import ActionType, ReminderIntent, TriggerType, parse_reminder


class TestParseReminder:
    """Tests para el parser NL."""
    
    def test_no_training_hours(self) -> None:
        """Detecta 'no entreno en X horas'."""
        intent = parse_reminder("avísame si no he entrenado en 48h")
        
        assert intent.trigger_type == TriggerType.CONDITIONAL
        assert intent.trigger_data["condition"] == "no_training"
        assert intent.trigger_data["hours"] == 48
        assert intent.action_type == ActionType.REMIND
        assert "last_workout" in intent.context_needed
    
    def test_no_training_days(self) -> None:
        """Detecta 'no entreno en X días'."""
        intent = parse_reminder("si no entreno en 2d")
        
        assert intent.trigger_type == TriggerType.CONDITIONAL
        assert intent.trigger_data["hours"] == 48  # 2 días = 48h
    
    def test_deload_warning(self) -> None:
        """Detecta aviso de deload."""
        intent = parse_reminder("avísame del deload 3 días antes")
        
        assert intent.trigger_type == TriggerType.EVENT_BASED
        assert intent.trigger_data["event"] == "deload"
        assert intent.trigger_data["days_before"] == 3
    
    def test_next_session_query(self) -> None:
        """Detecta consulta de próximo entreno."""
        intent = parse_reminder("qué toca hoy")
        
        assert intent.trigger_type == TriggerType.TIME_BASED
        assert intent.action_type == ActionType.ASK
    
    def test_to_cron_job_conditional(self) -> None:
        """Convierte a config de cron job."""
        intent = parse_reminder("avísame si no entreno en 48h")
        job = intent.to_cron_job()
        
        assert job["type"] == "conditional"
        assert job["condition"] == "no_training"
        assert job["threshold_hours"] == 48
        assert "context" in job
