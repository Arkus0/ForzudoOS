"""Webhook handler para Telegram Bot.

Este módulo procesa actualizaciones de Telegram y las enruta al bot de ForzudoOS.
"""

from __future__ import annotations

import json
import os
from typing import Any

from forzudo.telegram_bot import process_telegram_message


def handle_telegram_update(update: dict[str, Any]) -> dict:
    """Procesa una actualización de Telegram.
    
    Args:
        update: Objeto Update de Telegram Bot API
        
    Returns:
        Respuesta para enviar de vuelta a Telegram
    """
    # Extraer mensaje
    message = update.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("username", "juan")
    
    if not text:
        return {
            "chat_id": chat_id,
            "text": "No entendí el mensaje. Intenta con /ayuda",
        }
    
    # Procesar con el bot
    response_text = process_telegram_message(text, user_id)
    
    return {
        "chat_id": chat_id,
        "text": response_text,
        "parse_mode": "Markdown",
    }


def send_telegram_message(chat_id: int, text: str) -> bool:
    """Envía un mensaje a Telegram.
    
    Esta función se usa desde los cron jobs para enviar notificaciones.
    """
    import requests
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN no configurado")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.ok
    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")
        return False


def notify_user(user_id: str, message: str) -> bool:
    """Notifica a un usuario específico.
    
    Mapea user_id a chat_id y envía el mensaje.
    """
    # Mapeo simple de usuarios a chat_ids
    # En producción, esto vendría de una base de datos
    user_chat_map = {
        "juan": os.environ.get("TELEGRAM_CHAT_ID_JUAN"),
    }
    
    chat_id = user_chat_map.get(user_id)
    if not chat_id:
        print(f"❌ No se encontró chat_id para usuario: {user_id}")
        return False
    
    return send_telegram_message(int(chat_id), message)
