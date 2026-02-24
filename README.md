# ForzudoOS 🦍

Sistema híbrido de recordatorios inteligentes + dashboard para forzudos.

**Independiente de BBD Analytics** - Usa sus propias bases de datos en Notion.

## ¿Qué es?

Un sistema que entiende recordatorios en lenguaje natural y los enriquece con contexto de tu entrenamiento:

- **Parser NL**: Entiende frases como "avísame si no entreno en 48h"
- **Context Engine**: Calcula estado del ciclo 5/3/1, próximos pesos, alertas
- **Notion Integration**: Almacena recordatorios y entrenos en bases de datos propias
- **Scheduler**: Cron jobs que verifican condiciones
- **Dashboard**: Vista unificada HTML (GitHub Pages o local)
- **Telegram Bot**: Interacción rápida por mensajes

## Setup Inicial

### 1. Crear bases de datos en Notion

```bash
export NOTION_TOKEN="tu-token-de-notion"
uv run forzudo setup --parent-page "ID_DE_TU_PAGINA"
```

### 2. Configurar variables de entorno

```bash
# .env
NOTION_TOKEN="secret_xxx"
FORZUDO_REMINDERS_DB="xxx"
FORZUDO_WORKOUTS_DB="xxx"

# Opcional: para notificaciones por Telegram
TELEGRAM_BOT_TOKEN="xxx"
TELEGRAM_CHAT_ID_JUAN="xxx"
```

## Uso

### CLI

```bash
# Ver estado actual
uv run forzudo status

# Parsear frase
uv run forzudo parse "avísame si no he entrenado en 48h"

# Crear recordatorio
uv run forzudo recordar "avísame del deload 3 días antes"

# Ejecutar checks
uv run forzudo check

# Generar dashboard
uv run forzudo dashboard

# Probar bot
uv run forzudo bot "/hoy"
uv run forzudo bot "qué toca hoy"
```

### Telegram Bot

El bot responde a comandos y lenguaje natural:

| Comando | Descripción |
|---------|-------------|
| `/hoy` | Qué toca entrenar hoy |
| `/estado` | Resumen del ciclo 5/3/1 |
| `/hecho` | Marcar entreno completado |
| `/manana` | Mover entreno a mañana |
| `/recordar [frase]` | Crear recordatorio |
| `/alertas` | Ver alertas activas |
| `/pesos` | Ver pesos esperados |
| `/ayuda` | Mostrar ayuda |

**Lenguaje natural también funciona:**
- "avísame si no entreno en 48h"
- "qué toca hoy"
- "cuándo es el deload"

### Dashboard

```bash
# Generar datos
uv run forzudo dashboard

# Servir localmente
python -m http.server 8080 --directory docs/

# Abrir http://localhost:8080
```

## Arquitectura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Parser    │────>│  Scheduler  │────>│  OpenClaw   │
│     NL      │     │             │     │    Cron     │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           ▼
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐      ┌──────────┐      ┌──────────┐
   │  Notion │      │Telegram  │      │ Dashboard│
   │  (store)│      │   Bot    │      │  (HTML)  │
   └─────────┘      └──────────┘      └──────────┘
```

## Cron Jobs Activos

| Job | Frecuencia | Descripción |
|-----|------------|-------------|
| Check Workouts | Cada 6h | Verifica recordatorios pendientes |
| Daily Summary | 7:00 AM | Envía resumen diario |
| Deload Warning | Cada 24h | Avisa cuando se acerca el deload |

## Comandos del Bot - Ejemplos

```bash
# Ver qué toca hoy
$ uv run forzudo bot "/hoy"
💪 *Día 1 - OHP*
_Press + Hombros_
📊 Semana 5s (Macro 1)
*Sets:*
  1. `38kg` × 5
  2. `44kg` × 5
  3. `50kg` × 5+

# Estado del ciclo
$ uv run forzudo bot "/estado"
📊 *Estado del Ciclo*
*Macro:* 1
*Semana:* Semana 5s
*Posición:* 1/7
⏰ Deload en 6 días

# Lenguaje natural
$ uv run forzudo bot "avísame si no entreno en 48h"
📝 Detecté un recordatorio...
Para crearlo, usa: `/recordar avísame si no entreno en 48h`
```

## Desarrollo

```bash
# Tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format .

# Type check
uv run ty check src/
```

## Roadmap

- [x] Parser NL básico
- [x] Cálculos 5/3/1 independientes
- [x] Integración Notion
- [x] Scheduler con cron jobs
- [x] Dashboard HTML estático
- [x] Telegram Bot
- [ ] Sincronización automática desde BBD

## Stack

- Python 3.11+
- uv, ruff, ty, pytest
- Notion API
- OpenClaw Cron
- HTML/CSS/JS vanilla

---

*Para forzudos que odian las apps genéricas.*
