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
- **Telegram Bot**: Interacción rápida (próximamente)

## Setup Inicial

### 1. Crear bases de datos en Notion

```bash
# Necesitas el ID de una página en Notion donde crear las bases de datos
# La URL tiene formato: https://notion.so/workspace/[PAGE_ID]

export NOTION_TOKEN="tu-token-de-notion"
uv run forzudo setup --parent-page "ID_DE_TU_PAGINA"
```

Esto crea:
- 🦍 **ForzudoOS - Recordatorios**: Base de datos de recordatorios
- 🦍 **ForzudoOS - Entrenos**: Base de datos de entrenos (sincronizada desde BBD)

### 2. Configurar variables de entorno

```bash
# .env
NOTION_TOKEN="secret_xxx"
FORZUDO_PARENT_PAGE="xxx"        # Página padre (opcional tras setup)
FORZUDO_REMINDERS_DB="xxx"       # ID de la base de recordatorios
FORZUDO_WORKOUTS_DB="xxx"        # ID de la base de entrenos
```

## Uso

### CLI

```bash
# Ver estado actual (usa datos de Notion si están configurados)
uv run forzudo status

# Parsear una frase (sin crear recordatorio)
uv run forzudo parse "avísame si no he entrenado en 48h"

# Crear un recordatorio
uv run forzudo recordar "avísame del deload 3 días antes"

# Ejecutar checks de recordatorios
uv run forzudo check

# Sincronizar entreno desde BBD Analytics
uv run forzudo sync --data '{"exercise":"Bench","date":"2026-02-25",...}'

# Generar datos para dashboard
uv run forzudo dashboard

# Gestión de cron jobs
uv run forzudo cron list
uv run forzudo cron export
```

### Dashboard

El dashboard es una aplicación HTML/JS estática que puede funcionar de dos formas:

#### Opción 1: Local (recomendado para repos privados)

```bash
# Generar datos
uv run forzudo dashboard

# Servir localmente
python -m http.server 8080 --directory docs/

# Abrir en navegador
open http://localhost:8080
```

#### Opción 2: GitHub Pages (requiere repo público o plan Pro)

Si tu repo es público, GitHub Pages funciona gratis. Si es privado, necesitas GitHub Pro.

Para habilitar:
1. Settings → Pages → Source → Deploy from branch
2. Selecciona `main` y carpeta `/docs`
3. Guarda

## Arquitectura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Parser    │────>│  Scheduler  │────>│  OpenClaw   │
│     NL      │     │             │     │    Cron     │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Context Engine │
                  │   (5/3/1 calc)  │
                  └────────┬────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │  Notion  │  │ Dashboard│  │ Telegram │
      │  (store) │  │  (HTML)  │  │   (bot)  │
      └──────────┘  └──────────┘  └──────────┘
```

**Nota importante**: ForzudoOS **nunca modifica** BBD Analytics. Solo lee datos o recibe sincronizaciones manuales.

## Cron Jobs Activos

ForzudoOS registra automáticamente 3 cron jobs en OpenClaw:

| Job | Frecuencia | Descripción |
|-----|------------|-------------|
| Check Workouts | Cada 6h | Verifica recordatorios pendientes |
| Daily Summary | 7:00 AM | Envía resumen diario |
| Deload Warning | Cada 24h | Avisa cuando se acerca el deload |

## Desarrollo

```bash
# Tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format .

# Type check
uv run ty check src/

# Generar datos para dashboard
uv run forzudo dashboard
```

## Roadmap

- [x] Parser NL básico
- [x] Cálculos 5/3/1 independientes
- [x] Integración Notion (bases de datos propias)
- [x] Scheduler con cron jobs
- [x] Dashboard HTML estático
- [ ] Telegram Bot
- [ ] Sincronización automática desde BBD

## Stack

- Python 3.11+
- uv (gestión de dependencias)
- ruff (lint/format)
- ty (type checking)
- pytest (testing)
- Notion API
- OpenClaw Cron
- HTML/CSS/JS vanilla (dashboard)

---

*Para forzudos que odian las apps genéricas.*
