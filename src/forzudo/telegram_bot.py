"""Telegram Bot para ForzudoOS.

Integración con el bot de Telegram de OpenClaw para comandos interactivos.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class BotCommand:
    """Comando del bot."""
    name: str
    description: str
    handler: str  # Nombre del método handler


class ForzudoBot:
    """Bot de Telegram para ForzudoOS."""
    
    COMMANDS = [
        BotCommand("hoy", "Qué toca hoy", "cmd_hoy"),
        BotCommand("estado", "Resumen del ciclo", "cmd_estado"),
        BotCommand("hecho", "Marcar entreno completado", "cmd_hecho"),
        BotCommand("manana", "Mover entreno a mañana", "cmd_manana"),
        BotCommand("recordar", "Crear recordatorio", "cmd_recordar"),
        BotCommand("alertas", "Ver alertas activas", "cmd_alertas"),
        BotCommand("pesos", "Ver pesos esperados", "cmd_pesos"),
        BotCommand("ayuda", "Mostrar ayuda", "cmd_ayuda"),
    ]
    
    def __init__(self, user_id: str = "juan") -> None:
        self.user_id = user_id
    
    def process_message(self, message: str) -> str:
        """Procesa un mensaje recibido y devuelve respuesta."""
        message = message.strip().lower()
        
        # Detectar comando
        if message.startswith("/"):
            parts = message[1:].split(maxsplit=1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            
            return self.handle_command(command, args)
        
        # Mensaje natural (sin comando)
        return self.handle_natural_language(message)
    
    def handle_command(self, command: str, args: str) -> str:
        """Maneja un comando específico."""
        handlers = {
            "hoy": self.cmd_hoy,
            "estado": self.cmd_estado,
            "hecho": self.cmd_hecho,
            "manana": self.cmd_manana,
            "recordar": self.cmd_recordar,
            "alertas": self.cmd_alertas,
            "pesos": self.cmd_pesos,
            "ayuda": self.cmd_ayuda,
            "start": self.cmd_start,
        }
        
        handler = handlers.get(command, self.cmd_unknown)
        return handler(args)
    
    def handle_natural_language(self, message: str) -> str:
        """Maneja mensaje en lenguaje natural."""
        from forzudo.parser import parse_reminder
        
        intent = parse_reminder(message)
        
        # Si parece un recordatorio, ofrecer crearlo
        if intent.trigger_type.name in ["CONDITIONAL", "EVENT_BASED"]:
            return (
                f"📝 Detecté un recordatorio:\n"
                f"   \"{intent.raw_text}\"\n\n"
                f"Tipo: {intent.trigger_type.name}\n"
                f"Para crearlo, usa:\n"
                f"`/recordar {intent.raw_text}`"
            )
        
        # Si es consulta de estado
        if "toca" in message or "hoy" in message:
            return self.cmd_hoy("")
        
        return (
            "🤔 No entendí bien. Prueba con:\n"
            "• `/hoy` - Ver qué toca hoy\n"
            "• `/estado` - Resumen del ciclo\n"
            "• `/ayuda` - Ver todos los comandos"
        )
    
    # =================================================================
    # COMANDOS
    # =================================================================
    
    def cmd_start(self, args: str) -> str:
        """Comando /start."""
        return (
            "🦍 ¡Bienvenido a ForzudoOS!\n\n"
            "Soy tu asistente de entrenamiento 5/3/1.\n\n"
            "Comandos principales:\n"
            "• /hoy - Qué toca entrenar hoy\n"
            "• /estado - Estado del ciclo\n"
            "• /hecho - Marcar entreno completado\n"
            "• /alertas - Ver alertas\n\n"
            "Escribe /ayuda para ver todos los comandos."
        )
    
    def cmd_hoy(self, args: str) -> str:
        """Comando /hoy - Qué toca hoy."""
        from forzudo.context import build_context
        
        # Intentar obtener último entreno
        last_workout = None
        try:
            workouts_db = os.environ.get("FORZUDO_WORKOUTS_DB")
            if workouts_db:
                from forzudo.notion import get_last_workout
                last_workout = get_last_workout(workouts_db)
        except Exception:
            pass
        
        ctx = build_context(last_workout)
        
        if ctx.is_deload_week:
            return (
                "🧘 *Semana de Deload*\n\n"
                "Hoy es día de recuperación.\n"
                "Descansa, come bien, duerme.\n\n"
                f"Próximo ciclo comienza en {ctx.days_until_deload} días."
            )
        
        ns = ctx.next_session
        
        lines = [
            f"💪 *{ns['day_name']}*",
            f"_{ns['focus']}_",
            "",
            f"📊 {ns['week_name']} (Macro {ns['macro_num']})",
            "",
            "*Sets:*",
        ]
        
        for i, s in enumerate(ns['working_sets'], 1):
            lines.append(f"  {i}. `{s['weight']:.0f}kg` × {s['reps']}")
        
        if ctx.last_workout:
            hours = ctx.hours_since_last
            if hours and hours > 24:
                lines.append(f"\n⚠️ Último entreno: hace {hours:.0f}h")
        
        return "\n".join(lines)
    
    def cmd_estado(self, args: str) -> str:
        """Comando /estado - Resumen del ciclo."""
        from forzudo.context import build_context
        
        ctx = build_context()
        cs = ctx.cycle_state
        
        lines = [
            "📊 *Estado del Ciclo*",
            "",
            f"*Macro:* {cs.macro_num}",
            f"*Semana:* {cs.week_name}",
            f"*Posición:* {cs.week_in_macro}/7",
            f"*TM Bumps:* {cs.tm_bumps_completed}",
        ]
        
        if ctx.days_until_deload is not None:
            if ctx.days_until_deload == 0:
                lines.append("\n🧘 *Deload esta semana*")
            else:
                lines.append(f"\n⏰ Deload en {ctx.days_until_deload} días")
        
        if ctx.missed_workout:
            lines.append(f"\n⚠️ Llevas {ctx.hours_since_last:.0f}h sin entrenar")
        
        return "\n".join(lines)
    
    def cmd_hecho(self, args: str) -> str:
        """Comando /hecho - Marcar entreno completado."""
        # Aquí se integraría con Notion para registrar el entreno
        return (
            "✅ *Entreno registrado*\n\n"
            "¡Buen trabajo, forzudo!\n\n"
            "Para sincronizar con Notion, usa:\n"
            "`forzudo sync --data '{...}'`"
        )
    
    def cmd_manana(self, args: str) -> str:
        """Comando /manana - Mover entreno a mañana."""
        return (
            "📅 *Entreno movido a mañana*\n\n"
            "Descansa hoy, mañana te espera:\n"
        ) + self.cmd_hoy("")
    
    def cmd_recordar(self, args: str) -> str:
        """Comando /recordar - Crear recordatorio."""
        if not args:
            return (
                "📝 *Crear recordatorio*\n\n"
                "Uso: `/recordar [frase]`\n\n"
                "Ejemplos:\n"
                "• `/recordar avísame si no entreno en 48h`\n"
                "• `/recordar avísame del deload 3 días antes`"
            )
        
        from forzudo.parser import parse_reminder
        from forzudo.scheduler import Scheduler
        
        intent = parse_reminder(args)
        scheduler = Scheduler()
        job = scheduler.create_job(self.user_id, intent)
        
        return (
            f"✅ *Recordatorio creado*\n\n"
            f"ID: `{job.id}`\n"
            f"Tipo: {intent.trigger_type.name}\n"
            f"Estado: {job.status.value}\n\n"
            f"Te avisaré cuando se cumpla la condición."
        )
    
    def cmd_alertas(self, args: str) -> str:
        """Comando /alertas - Ver alertas activas."""
        from forzudo.context import build_context
        
        ctx = build_context()
        alerts = []
        
        if ctx.days_until_deload is not None and ctx.days_until_deload <= 3:
            alerts.append(f"⏰ Deload en {ctx.days_until_deload} días")
        
        if ctx.missed_workout:
            alerts.append(f"⚠️ Llevas {ctx.hours_since_last:.0f}h sin entrenar")
        
        if ctx.is_deload_week:
            alerts.append("🧘 Semana de deload - recuperación")
        
        if not alerts:
            return "✅ *Sin alertas*\n\nTodo en orden, forzudo."
        
        return "🔔 *Alertas:*\n\n" + "\n".join(f"• {a}" for a in alerts)
    
    def cmd_pesos(self, args: str) -> str:
        """Comando /pesos - Ver pesos esperados."""
        from forzudo.context import build_context
        
        ctx = build_context()
        ns = ctx.next_session
        
        lines = [
            f"🏋️ *Pesos para {ns['day_name']}*",
            f"_{ns['week_name']}_",
            "",
        ]
        
        for i, s in enumerate(ns['working_sets'], 1):
            pct = int(s['pct'] * 100)
            lines.append(f"{i}. `{s['weight']:.0f}kg` × {s['reps']} ({pct}%)")
        
        return "\n".join(lines)
    
    def cmd_ayuda(self, args: str) -> str:
        """Comando /ayuda - Mostrar ayuda."""
        lines = [
            "🦍 *ForzudoOS - Comandos*",
            "",
            "*Entrenamiento:*",
            "• /hoy - Qué toca hoy",
            "• /estado - Resumen del ciclo",
            "• /hecho - Marcar entreno hecho",
            "• /manana - Mover a mañana",
            "• /pesos - Ver pesos esperados",
            "",
            "*Recordatorios:*",
            "• /recordar [frase] - Crear recordatorio",
            "• /alertas - Ver alertas",
            "",
            "También puedes escribirme en lenguaje natural:\n"
            "\"avísame si no entreno en 48h\"",
        ]
        
        return "\n".join(lines)
    
    def cmd_unknown(self, args: str) -> str:
        """Comando desconocido."""
        return (
            "❓ *Comando no reconocido*\n\n"
            "Prueba con:\n"
            "• /hoy - Qué toca hoy\n"
            "• /estado - Resumen del ciclo\n"
            "• /ayuda - Ver todos los comandos"
        )


def process_telegram_message(message_text: str, user_id: str = "juan") -> str:
    """Función pública para procesar mensajes de Telegram.
    
    Esta función es llamada por el webhook de Telegram o por OpenClaw.
    """
    bot = ForzudoBot(user_id)
    return bot.process_message(message_text)


def cmd_bot_test(args: list[str]) -> int:
    """Comando CLI para probar el bot."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Probar bot de Telegram")
    parser.add_argument("message", help="Mensaje a procesar")
    parser.add_argument("--user", default="juan", help="ID de usuario")
    pargs = parser.parse_args(args)
    
    response = process_telegram_message(pargs.message, pargs.user)
    print(response)
    return 0
